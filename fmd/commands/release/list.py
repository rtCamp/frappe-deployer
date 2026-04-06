from pathlib import Path
from typing import Optional

import typer

from fmd.commands._utils import load_config, build_runners, get_printer
from fmd.managers.release import ReleaseManager


def list_releases(
    bench_name: Optional[str] = typer.Argument(None, help="Bench name (required when no config file is provided)."),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to site config TOML file."),
):
    """List all releases, marking the currently active one."""
    overrides = {"site_name": bench_name} if bench_name else None
    config = load_config(config_path, overrides=overrides)
    printer = get_printer()
    image_runner, exec_runner, host_runner = build_runners(config)
    manager = ReleaseManager(config, image_runner, exec_runner, host_runner, printer)
    releases = manager.list_releases()
    if not releases:
        typer.echo("No releases found.")
        return
    for r in releases:
        marker = " (current)" if r["current"] else ""
        typer.echo(f"{r['name']}{marker}")
