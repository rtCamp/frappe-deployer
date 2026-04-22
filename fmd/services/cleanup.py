from pathlib import Path
import importlib
import shutil
from typing import Any

from fmd.consts import BACKUP_DIR_NAME, RELEASE_DIR_NAME
from fmd.runner.base import is_ci

_rich = None
try:
    _rich = importlib.import_module("rich")
    Console = importlib.import_module("rich.console").Console
    Confirm = importlib.import_module("rich.prompt").Confirm
    Prompt = importlib.import_module("rich.prompt").Prompt
    Table = importlib.import_module("rich.table").Table
except Exception:

    class Console:
        def print(self, *args, **kwargs):
            print(*args)

    class Confirm:
        @staticmethod
        def ask(*args, **kwargs):
            return True

    class Prompt:
        @staticmethod
        def ask(*args, **kwargs):
            return ""

    class Table(list):
        def __init__(self, *args, **kwargs):
            super().__init__()

        def add_column(self, *args, **kwargs):
            pass

        def add_row(self, *args, **kwargs):
            pass


class CleanupService:
    def __init__(self, runner: Any, host_runner: Any, config: Any, printer: Any):
        self.runner = runner
        self.host_runner = host_runner
        self.config = config
        self.printer = printer

    def get_dir_size(self, path: Path) -> str:
        try:
            output = self.host_runner.run_cmd(["du", "-sh", str(path)])
            stdout_lines = getattr(output, "stdout", None) or []
            if stdout_lines:
                first = stdout_lines[0]
                if isinstance(first, bytes):
                    first = first.decode(errors="replace")
                size_str = first.split()[0]
                return size_str
        except Exception:
            pass

        total = 0
        if path.is_file():
            return f"{path.stat().st_size / 1024 / 1024:.1f} MB"
        for p in path.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
        if total < 1024:
            return f"{total} B"
        elif total < 1024 * 1024:
            return f"{total / 1024:.1f} KB"
        elif total < 1024 * 1024 * 1024:
            return f"{total / 1024 / 1024:.1f} MB"
        else:
            return f"{total / 1024 / 1024 / 1024:.2f} GB"

    def cleanup_releases(self, workspace_root: Path, bench_path: Path):
        retain_limit = self.config.release.releases_retain_limit
        current_release = bench_path.resolve()
        workspace = workspace_root / "workspace"
        release_dirs = [d for d in workspace.iterdir() if d.is_dir() and d.name.startswith(RELEASE_DIR_NAME)]
        release_dirs.sort(
            key=lambda x: int(x.name.split("_")[-1]) if x.name.split("_")[-1].isdigit() else 0, reverse=True
        )

        available = [d for d in release_dirs if d.resolve() != current_release]
        to_delete = available[retain_limit:]
        for d in to_delete:
            shutil.rmtree(d)
            self.printer.print(f"Removed old release: {d.name}")

    def cleanup_workspace_cache(
        self,
        workspace_root: Path,
        bench_path: Path,
        backup_retain_limit: int = 0,
        release_retain_limit: int = 0,
        auto_approve: bool = False,
        show_sizes: bool = False,
    ):
        console = Console()
        self.printer.stop()

        def print_items_table(items: list[Path], title: str) -> Table:
            table = Table(title=title)
            table.add_column("Index", justify="right", style="cyan")
            table.add_column("Name", style="magenta")
            if show_sizes:
                table.add_column("Size", style="green")
            table.add_column("Path", style="blue")

            for idx, item in enumerate(items, 1):
                row = [str(idx), item.name]
                if show_sizes:
                    size = self.get_dir_size(item)
                    row.append(size)
                row.append(str(item.absolute()))
                table.add_row(*row)

            console.print(table)
            return table

        def get_selected_indices(items: list[Path], prompt_text: str) -> list[int]:
            if not items:
                return []

            if auto_approve or is_ci():
                return list(range(len(items)))

            print_items_table(items, prompt_text)

            while True:
                selection = Prompt.ask(
                    f"\nEnter indices to delete (1-{len(items)}, 'all' for all, or empty to skip)", default=""
                )

                if not selection:
                    return []

                if selection.lower() == "all":
                    return list(range(len(items)))

                try:
                    indices = [int(i.strip()) - 1 for i in selection.split(",")]
                    if all(0 <= i < len(items) for i in indices):
                        return indices
                    console.print("[red]Invalid indices. Please try again.[/red]")
                except ValueError:
                    console.print("[red]Invalid input. Please enter numbers separated by commas or 'all'.[/red]")

        host_venv_path, _ = self.runner.venv_paths(workspace_root)
        cache_dir = host_venv_path.parent

        if not cache_dir.exists():
            console.print(f"\n[blue]Cache directory {cache_dir} doesn't exist - already clean[/blue]")
        else:
            size_info = f" ([green]{self.get_dir_size(cache_dir)}[/green])" if show_sizes else ""
            console.print("\n[yellow]Cache directory available for cleanup:[/yellow]")
            console.print(f"[magenta]{cache_dir.name}[/magenta]{size_info} - [blue]{cache_dir.absolute()}[/blue]")
            try:
                if auto_approve or Confirm.ask(f"Delete cache directory: {cache_dir}?"):
                    shutil.rmtree(cache_dir)
                    console.print(f"[green]Removed {cache_dir.absolute()} directory[/green]")
            except Exception as e:
                console.print(f"[red]Failed to remove {cache_dir.absolute()} directory: {str(e)}[/red]")

        prev_bench = workspace_root / "prev_frappe_bench"
        if not prev_bench.exists():
            console.print("\n[blue]Previous bench directory doesn't exist - already clean[/blue]")
        else:
            console.print("\n[yellow]Previous bench directory available for cleanup:[/yellow]")
            try:
                if auto_approve or Confirm.ask(f"Delete previous bench directory: {prev_bench}?"):
                    shutil.rmtree(prev_bench)
                    console.print(f"[green]Removed {prev_bench.absolute()} directory[/green]")
            except Exception as e:
                console.print(f"[red]Failed to remove {prev_bench.absolute()}: {str(e)}[/red]")

        backup_dir = workspace_root / BACKUP_DIR_NAME

        if backup_dir.exists():
            backup_dirs = [d for d in backup_dir.iterdir() if d.is_dir()]
            backup_dirs.sort(key=lambda x: x.name, reverse=True)

            if not backup_dirs:
                console.print("\n[blue]No backup directories found - already clean[/blue]")
            else:
                if backup_retain_limit > 0:
                    kept_backups = backup_dirs[:backup_retain_limit]
                    backups_to_remove = backup_dirs[backup_retain_limit:]

                    console.print(f"\n[green]Currently keeping {len(kept_backups)} recent backups:[/green]")
                    for backup in kept_backups:
                        console.print(f"[green]  • {backup.name}[/green]")

                    if backups_to_remove:
                        selected_indices = get_selected_indices(
                            backups_to_remove,
                            f"Backup directories to clean (keeping {backup_retain_limit} most recent)",
                        )

                        for idx in selected_indices:
                            backup_to_remove = backups_to_remove[idx]
                            try:
                                if auto_approve or Confirm.ask(f"Delete backup directory: {backup_to_remove.name}?"):
                                    shutil.rmtree(backup_to_remove)
                                    console.print(f"[green]Removed backup directory: {backup_to_remove.name}[/green]")
                            except Exception as e:
                                console.print(f"[red]Failed to remove {backup_to_remove.name}: {str(e)}[/red]")
                else:
                    console.print("\n[yellow]All backup directories available for cleanup:[/yellow]")
                    selected_indices = get_selected_indices(
                        backup_dirs, "Backup directories to clean (no retention limit)"
                    )

                    for idx in selected_indices:
                        backup_to_remove = backup_dirs[idx]
                        try:
                            if auto_approve or Confirm.ask(f"Delete backup directory: {backup_to_remove.name}?"):
                                shutil.rmtree(backup_to_remove)
                                console.print(f"[green]Removed backup directory: {backup_to_remove.name}[/green]")
                        except Exception as e:
                            console.print(f"[red]Failed to remove {backup_to_remove.name}: {str(e)}[/red]")
        else:
            console.print("\n[blue]No backup directory exists - already clean[/blue]")

        current_release = bench_path.resolve()
        workspace = workspace_root / "workspace"
        release_dirs = [d for d in workspace.iterdir() if d.is_dir() and d.name.startswith(RELEASE_DIR_NAME)]

        if not release_dirs:
            console.print("\n[blue]No release directories found - already clean[/blue]")
        else:
            release_dirs.sort(
                key=lambda x: int(x.name.split("_")[-1]) if x.name.split("_")[-1].isdigit() else 0, reverse=True
            )

            available_releases = [d for d in release_dirs if d.resolve() != current_release]
            if not available_releases:
                console.print("\n[blue]No release directories available for cleanup (excluding current release)[/blue]")
            else:
                if release_retain_limit > 0:
                    kept_releases = available_releases[:release_retain_limit]
                    releases_to_remove = available_releases[release_retain_limit:]

                    console.print(f"\n[green]Currently keeping {len(kept_releases)} recent releases:[/green]")
                    for rel in kept_releases:
                        console.print(f"[green]  • {rel.name}[/green]")

                    if releases_to_remove:
                        if auto_approve:
                            self.config.release.releases_retain_limit = release_retain_limit
                            self.cleanup_releases(workspace_root, bench_path)
                        else:
                            selected_indices = get_selected_indices(
                                releases_to_remove,
                                f"Release directories to clean (keeping {release_retain_limit} most recent)",
                            )
                            for idx in selected_indices:
                                release_to_remove = releases_to_remove[idx]
                                try:
                                    if Confirm.ask(f"Delete release directory: {release_to_remove.name}?"):
                                        shutil.rmtree(release_to_remove)
                                        console.print(
                                            f"[green]Removed release directory: {release_to_remove.name}[/green]"
                                        )
                                except Exception as e:
                                    console.print(
                                        f"[red]Failed to remove release {release_to_remove.name}: {str(e)}[/red]"
                                    )
                else:
                    console.print("\n[yellow]All release directories available for cleanup:[/yellow]")
                    selected_indices = get_selected_indices(
                        available_releases, "Release directories to clean (no retention limit)"
                    )

                    for idx in selected_indices:
                        release_to_remove = available_releases[idx]
                        try:
                            if auto_approve or Confirm.ask(f"Delete release directory: {release_to_remove.name}?"):
                                shutil.rmtree(release_to_remove)
                                console.print(f"[green]Removed release directory: {release_to_remove.name}[/green]")
                        except Exception as e:
                            console.print(f"[red]Failed to remove release {release_to_remove.name}: {str(e)}[/red]")
