from pathlib import Path
from typing import Optional

import typer

from fmd.commands._utils import build_runners, get_printer, load_config
from fmd.managers.release import ReleaseManager


def switch(
    config_path: Path = typer.Argument(..., help="Path to site config TOML file."),
    release_name: str = typer.Argument(..., help="Release directory name to switch to."),
    migrate: Optional[bool] = typer.Option(None, "--migrate/--no-migrate", help="Run bench migrate after switch."),
    migrate_timeout: Optional[int] = typer.Option(
        None, "--migrate-timeout", help="Migrate timeout in seconds.", show_default=False
    ),
    maintenance_mode: Optional[bool] = typer.Option(
        None, "--maintenance-mode/--no-maintenance-mode", help="Enable maintenance mode during switch."
    ),
    backups: Optional[bool] = typer.Option(None, "--backups/--no-backups", help="Take DB backup before switch."),
    rollback: Optional[bool] = typer.Option(None, "--rollback/--no-rollback", help="Roll back on failure."),
    search_replace: Optional[bool] = typer.Option(
        None, "--search-replace/--no-search-replace", help="Run search-and-replace in DB after restore."
    ),
    drain_workers: Optional[bool] = typer.Option(
        None, "--drain-workers/--no-drain-workers", help="Drain workers before restart."
    ),
    sync_workers: Optional[bool] = typer.Option(
        None, "--sync-workers/--no-sync-workers", help="Sync to remote workers after switch."
    ),
):
    """Switch live bench symlink to a previously-created release."""
    deploy: dict = {}
    if migrate is not None:
        deploy["migrate"] = migrate
    if migrate_timeout is not None:
        deploy["migrate_timeout"] = migrate_timeout
    if maintenance_mode is not None:
        deploy["maintenance_mode"] = maintenance_mode
    if backups is not None:
        deploy["backups"] = backups
    if rollback is not None:
        deploy["rollback"] = rollback
    if search_replace is not None:
        deploy["search_replace"] = search_replace
    if drain_workers is not None:
        deploy["drain_workers"] = drain_workers
    if sync_workers is not None:
        deploy["sync_workers"] = sync_workers

    overrides = {"deploy": deploy} if deploy else None
    config = load_config(config_path, overrides=overrides)
    printer = get_printer()
    image_runner, exec_runner, host_runner = build_runners(config)
    printer.start("Switching release")
    manager = ReleaseManager(config, image_runner, exec_runner, host_runner, printer)
    manager.switch(release_name)
    printer.stop()
    typer.echo(f"Switched to {release_name}.")
