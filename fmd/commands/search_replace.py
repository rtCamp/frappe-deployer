from pathlib import Path
from typing import Optional

import typer

from fmd.commands._utils import build_runners, get_printer, load_config
from fmd.managers.release import ReleaseManager


def search_replace(
    bench_name: Optional[str] = typer.Argument(None, help="Bench name (required when no config file is provided)."),
    search: str = typer.Argument(..., help="Text to search for."),
    replace: str = typer.Argument(..., help="Text to replace with."),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to site config TOML file."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would change without making changes."),
):
    """Search and replace text across all text fields in the Frappe database."""
    overrides = {"bench_name": bench_name, "site_name": bench_name} if bench_name else None
    config = load_config(config_path, overrides=overrides)
    printer = get_printer()
    image_runner, exec_runner, host_runner = build_runners(config)
    printer.start("Working")
    manager = ReleaseManager(config, image_runner, exec_runner, host_runner, printer)
    manager._search_and_replace_in_database(search, replace, dry_run)
    printer.stop()
