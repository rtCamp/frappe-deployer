from pathlib import Path

import typer

from fmd.commands._utils import build_runners, get_printer, load_config
from fmd.managers.release import ReleaseManager


def search_replace(
    config_path: Path = typer.Argument(..., help="Path to site config TOML file."),
    search: str = typer.Argument(..., help="Text to search for."),
    replace: str = typer.Argument(..., help="Text to replace with."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would change without making changes."),
):
    """Search and replace text across all text fields in the Frappe database."""
    config = load_config(config_path)
    printer = get_printer()
    image_runner, exec_runner, host_runner = build_runners(config)
    printer.start("Working")
    manager = ReleaseManager(config, image_runner, exec_runner, host_runner, printer)
    manager._search_and_replace_in_database(search, replace, dry_run)
    printer.stop()
