from pathlib import Path
from typing import List, Optional

import typer

from fmd.commands._utils import build_runners, get_printer, load_config, parse_app_option
from fmd.managers.ship import ShipManager


def ship(
    config_path: Path = typer.Argument(..., help="Path to site config TOML file."),
    site_name: Optional[str] = typer.Option(
        None, "--site-name", "-s", help="Site name (required when creating a new config file)."
    ),
    apps: List[str] = typer.Option(
        [], "--app", "-a", help="App in format org/repo:ref[:subdir_path]. Repeatable.", show_default=False
    ),
    github_token: Optional[str] = typer.Option(
        None, "--github-token", help="GitHub personal access token.", show_default=False
    ),
    python_version: Optional[str] = typer.Option(
        None, "--python-version", "-p", help="Python version for venv.", show_default=False
    ),
    uv: Optional[bool] = typer.Option(None, "--uv/--no-uv", help="Use uv instead of pip."),
    migrate: Optional[bool] = typer.Option(None, "--migrate/--no-migrate", help="Run bench migrate on switch."),
    migrate_timeout: Optional[int] = typer.Option(
        None, "--migrate-timeout", help="Migrate timeout in seconds.", show_default=False
    ),
    maintenance_mode: Optional[bool] = typer.Option(
        None, "--maintenance-mode/--no-maintenance-mode", help="Enable maintenance mode during deploy."
    ),
    backups: Optional[bool] = typer.Option(None, "--backups/--no-backups", help="Take DB backup before switch."),
    rollback: Optional[bool] = typer.Option(
        None, "--rollback/--no-rollback", help="Roll back to previous release on failure."
    ),
    search_replace: Optional[bool] = typer.Option(
        None, "--search-replace/--no-search-replace", help="Run search-and-replace in DB after restore."
    ),
    drain_workers: Optional[bool] = typer.Option(
        None, "--drain-workers/--no-drain-workers", help="Drain workers before restart."
    ),
    sync_workers: Optional[bool] = typer.Option(
        None, "--sync-workers/--no-sync-workers", help="Sync to remote workers after deploy."
    ),
    releases_retain_limit: Optional[int] = typer.Option(
        None, "--releases-retain-limit", help="Number of releases to retain.", show_default=False
    ),
    symlink_subdir_apps: Optional[bool] = typer.Option(
        None, "--symlink-subdir-apps/--no-symlink-subdir-apps", help="Symlink all subdir apps."
    ),
):
    """Ship deploy: create release locally → rsync to remote → switch on remote."""
    overrides: dict = {}
    if site_name is not None:
        overrides["site_name"] = site_name
    if apps:
        overrides["apps"] = parse_app_option(apps)
    if github_token is not None:
        overrides["github_token"] = github_token
    if python_version is not None:
        overrides["python_version"] = python_version
    if uv is not None:
        overrides["uv"] = uv

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

    release: dict = {}
    if releases_retain_limit is not None:
        release["releases_retain_limit"] = releases_retain_limit
    if symlink_subdir_apps is not None:
        release["symlink_subdir_apps"] = symlink_subdir_apps
    if release:
        overrides["release"] = release

    config = load_config(config_path, overrides=overrides or None, create_if_missing=True)
    printer = get_printer()

    if not config.ship:
        typer.echo("Error: config has no [ship] section.", err=True)
        raise typer.Exit(code=1)

    printer.start("Shipping")
    manager = ShipManager(config, printer)
    manager.deploy(config_path.resolve())
    printer.stop()
    typer.echo("Ship complete.")
