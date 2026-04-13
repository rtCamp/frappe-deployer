from pathlib import Path
from typing import Optional
import threading

import typer
from typer_examples import example

try:
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
except ImportError:
    Console = None
    Table = None
    Live = None

from fmd.commands._utils import get_printer
from fmd.consts import RELEASE_DIR_NAME
from fmd.runner.base import is_ci
from fmd.runner.host import HostRunner

try:
    from frappe_manager import CLI_BENCHES_DIRECTORY
except Exception:
    CLI_BENCHES_DIRECTORY = Path("/workspace")


@example(
    "List from config file",
    "--config {config_path}",
    detail="Reads bench name from config and lists all releases with metadata.",
    config_path="./site.toml",
)
@example(
    "List releases by bench name",
    "{bench_name}",
    detail="Lists all releases in the bench workspace, marking the currently active one.",
    bench_name="mybench",
)
def list_releases(
    bench_name: Optional[str] = typer.Argument(None, help="Bench name (required when no config file is provided)."),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to site config TOML file."),
):
    """List all releases, marking the currently active one."""

    if config_path and config_path.exists():
        try:
            import toml
        except Exception:
            try:
                import tomllib as toml
            except Exception:
                import json as toml

        config_data = toml.loads(config_path.read_text())
        bench_name_from_config = config_data.get("bench_name", config_data.get("site_name", bench_name))

        ship_config = config_data.get("ship")
        if ship_config:
            workspace_root = config_path.parent
        else:
            workspace_root = CLI_BENCHES_DIRECTORY / bench_name_from_config
    elif bench_name:
        workspace_root = CLI_BENCHES_DIRECTORY / bench_name
    else:
        typer.echo("Error: bench_name argument or --config/-c is required.")
        raise typer.Exit(1)

    workspace = workspace_root / "workspace"
    bench_path = workspace / "frappe-bench"

    if not workspace.exists():
        typer.echo("No releases found.")
        return

    release_dirs = sorted(
        [d for d in workspace.iterdir() if d.is_dir() and d.name.startswith(RELEASE_DIR_NAME)],
        key=lambda d: d.name,
        reverse=True,
    )

    if not release_dirs:
        typer.echo("No releases found.")
        return

    if not (Console and Table and Live) or is_ci():
        current_release = bench_path.resolve() if bench_path.is_symlink() else None
        for d in release_dirs:
            marker = " (current)" if current_release and d.resolve() == current_release else ""
            typer.echo(f"{d.name}{marker}")
        return

    console = Console()

    current_release = bench_path.resolve() if bench_path.is_symlink() else None
    rows = {}
    rows_lock = threading.Lock()
    live_ref = {"live": None}

    for i, d in enumerate(release_dirs):
        rows[i] = {
            "status": " ",
            "name": d.name,
            "size": "[dim]Loading...[/dim]",
            "python": "[dim]...[/dim]",
            "node": "[dim]...[/dim]",
            "apps": "[dim]...[/dim]",
            "symlinks": "[dim]...[/dim]",
        }

    def make_table():
        table = Table(title="Releases", show_header=True)
        table.add_column("Status", style="cyan", width=8)
        table.add_column("Release Name", style="magenta")
        table.add_column("Size", style="yellow", justify="right")
        table.add_column("Python", style="blue", justify="center")
        table.add_column("Node", style="blue", justify="center")
        table.add_column("Apps", style="green", justify="center")
        table.add_column("Symlink Status", style="white")

        with rows_lock:
            for i in range(len(release_dirs)):
                row = rows[i]
                table.add_row(
                    row["status"],
                    row["name"],
                    row["size"],
                    row["python"],
                    row["node"],
                    row["apps"],
                    row["symlinks"],
                )
        return table

    def collect_metadata(release_dir: Path, index: int):
        from fmd.services.cleanup import CleanupService

        apps_dir = release_dir / "apps"
        app_count = 0
        broken_symlinks = []

        if apps_dir.exists():
            for item in apps_dir.iterdir():
                if item.name in [".DS_Store", "__pycache__"]:
                    continue
                app_count += 1
                if item.is_symlink() and not item.exists():
                    broken_symlinks.append(item.name)

        size = "N/A"
        try:
            _hr = HostRunner(verbose=False, printer=get_printer())
            output = _hr.run_cmd(["du", "-sh", str(release_dir)])
            stdout_lines = getattr(output, "stdout", None) or []
            if stdout_lines:
                first = stdout_lines[0]
                if isinstance(first, bytes):
                    first = first.decode(errors="replace")
                size = first.split()[0]
        except Exception:
            pass

        python_version = "N/A"
        uv_default = release_dir / ".uv" / "python-default"
        if uv_default.is_symlink():
            try:
                target = uv_default.readlink()
                parts = str(target).split("/")
                for part in parts:
                    if part.startswith("cpython-") or part.startswith("python-"):
                        version_part = part.replace("cpython-", "").replace("python-", "")
                        python_version = version_part.split("-")[0]
                        break
            except Exception:
                pass

        node_version = "N/A"
        fnm_default = release_dir / ".fnm" / "aliases" / "default"
        if fnm_default.is_symlink():
            try:
                target = fnm_default.readlink()
                parts = str(target).split("/")
                for part in parts:
                    if part.startswith("v") and part[1:].replace(".", "").isdigit():
                        node_version = part[1:]
                        break
            except Exception:
                pass

        if node_version == "N/A":
            node_versions_dir = release_dir / ".fnm" / "node-versions"
            if node_versions_dir.exists():
                try:
                    versions = [d.name for d in node_versions_dir.iterdir() if d.is_dir() and d.name.startswith("v")]
                    if versions:
                        node_version = versions[0][1:]
                except Exception:
                    pass

        is_current = current_release is not None and release_dir.resolve() == current_release

        return {
            "index": index,
            "current": is_current,
            "size": size,
            "python_version": python_version,
            "node_version": node_version,
            "app_count": app_count,
            "broken_symlinks": broken_symlinks,
        }

    def on_release_loaded(result):
        index = result["index"]
        status = "[green]●[/green]" if result["current"] else " "
        broken = result.get("broken_symlinks", [])
        if broken:
            symlink_status = f"[red]✗ {len(broken)} broken[/red]"
        else:
            symlink_status = "[green]✓ OK[/green]"

        with rows_lock:
            rows[index]["status"] = status
            rows[index]["size"] = result.get("size", "N/A")
            rows[index]["python"] = result.get("python_version", "N/A")
            rows[index]["node"] = result.get("node_version", "N/A")
            rows[index]["apps"] = str(result.get("app_count", 0))
            rows[index]["symlinks"] = symlink_status

        if live_ref["live"]:
            live_ref["live"].update(make_table())

    with Live(make_table(), console=console, refresh_per_second=10) as live:
        live_ref["live"] = live

        from concurrent.futures import ThreadPoolExecutor, as_completed
        import os

        max_workers = min(len(release_dirs), os.cpu_count() or 4)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(collect_metadata, d, i) for i, d in enumerate(release_dirs)]

            results = []
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    on_release_loaded(result)
                except Exception as e:
                    console.print(f"[red]Error loading release: {e}[/red]")

    broken_count = sum(1 for r in results if r.get("broken_symlinks"))
    if broken_count > 0:
        console.print(f"\n[yellow]Warning: {broken_count} release(s) have broken symlinks[/yellow]")
