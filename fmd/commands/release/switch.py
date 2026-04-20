from pathlib import Path
from typing import Optional

import typer
from typer_examples import example

from fmd.commands._utils import build_runners, get_printer, load_config
from fmd.managers.release import ReleaseManager


@example(
    "Switch with maintenance mode",
    "{bench_name} {release_name} --maintenance-mode",
    detail="Enables maintenance mode during the switch to prevent user-facing errors while the symlink is updated.",
    bench_name="mybench",
    release_name="release_20240101_120000",
)
@example(
    "Switch with migrate",
    "{bench_name} {release_name} --migrate",
    detail="Runs bench migrate after switching the symlink to apply any pending schema changes.",
    bench_name="mybench",
    release_name="release_20240101_120000",
)
@example(
    "Switch to a release",
    "{bench_name} {release_name}",
    detail="Updates the live bench symlink to point at the specified release directory.",
    bench_name="mybench",
    release_name="release_20240101_120000",
)
def switch(
    bench_name: Optional[str] = typer.Argument(None, help="Bench name (required when no config file is provided)."),
    release_name: str = typer.Argument(..., help="Release directory name to switch to."),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to site config TOML file."),
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
    overrides: dict = {}
    if bench_name is not None:
        overrides["bench_name"] = bench_name
        if "site_name" not in overrides:
            overrides["site_name"] = bench_name

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
    if deploy:
        overrides["deploy"] = deploy

    config = load_config(config_path, overrides=overrides or None, skip_repo_validation=True)
    printer = get_printer()
    image_runner, exec_runner, host_runner = build_runners(config)
    printer.start("Switching release")
    manager = ReleaseManager(config, image_runner, exec_runner, host_runner, printer)
    manager.switch(release_name)
    printer.stop()
    typer.echo(f"Switched to {release_name}.")
