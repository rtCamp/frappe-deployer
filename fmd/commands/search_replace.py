from pathlib import Path
from typing import Optional

import typer
from typer_examples import example

from fmd.commands._utils import build_runners, get_printer, load_config
from fmd.managers.release import ReleaseManager


@example(
    "Dry-run search-replace",
    "{bench_name} {search} {replace} --dry-run",
    detail="Shows what would be changed without modifying the database.",
    bench_name="mybench",
    search="https://old.example.com",
    replace="https://new.example.com",
)
@example(
    "Search and replace in DB",
    "{bench_name} {search} {replace}",
    detail="Replaces all occurrences of the search text across all text fields in the Frappe database.",
    bench_name="mybench",
    search="https://old.example.com",
    replace="https://new.example.com",
)
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
