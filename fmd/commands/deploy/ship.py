from pathlib import Path
from typing import List, Optional

import typer

from fmd.commands._utils import build_runners, get_printer, load_config, parse_app_option
from fmd.managers.ship import ShipManager


def ship(
    bench_name: Optional[str] = typer.Argument(None, help="Bench name (required when no config file is provided)."),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to site config TOML file."),
    apps: List[str] = typer.Option(
        [], "--app", "-a", help="App in format org/repo:ref[:subdir_path]. Repeatable.", show_default=False
    ),
    github_token: Optional[str] = typer.Option(
        None, "--github-token", help="GitHub personal access token.", show_default=False
    ),
    uv: Optional[bool] = typer.Option(None, "--uv/--no-uv", help="Use uv instead of pip."),
    python_version: Optional[str] = typer.Option(
        None,
        "--python-version",
        "-p",
        help="Python version for venv.",
        show_default=False,
        rich_help_panel="Release Options",
    ),
    node_version: Optional[str] = typer.Option(
        None,
        "--node-version",
        "-n",
        help="Node.js version to install via fnm.",
        show_default=False,
        rich_help_panel="Release Options",
    ),
    releases_retain_limit: Optional[int] = typer.Option(
        None,
        "--releases-retain-limit",
        help="Number of releases to retain.",
        show_default=False,
        rich_help_panel="Release Options",
    ),
    symlink_subdir_apps: Optional[bool] = typer.Option(
        None,
        "--symlink-subdir-apps/--no-symlink-subdir-apps",
        help="Symlink all subdir apps.",
        rich_help_panel="Release Options",
    ),
    runner_image: Optional[str] = typer.Option(
        None,
        "--runner-image",
        help="Docker image to use for release creation. Overrides auto-detection.",
        show_default=False,
        rich_help_panel="Release Options",
    ),
    migrate: Optional[bool] = typer.Option(
        None, "--migrate/--no-migrate", help="Run bench migrate on switch.", rich_help_panel="Switch Options"
    ),
    migrate_timeout: Optional[int] = typer.Option(
        None,
        "--migrate-timeout",
        help="Migrate timeout in seconds.",
        show_default=False,
        rich_help_panel="Switch Options",
    ),
    maintenance_mode: Optional[bool] = typer.Option(
        None,
        "--maintenance-mode/--no-maintenance-mode",
        help="Enable maintenance mode during deploy.",
        rich_help_panel="Switch Options",
    ),
    backups: Optional[bool] = typer.Option(
        None, "--backups/--no-backups", help="Take DB backup before switch.", rich_help_panel="Switch Options"
    ),
    rollback: Optional[bool] = typer.Option(
        None,
        "--rollback/--no-rollback",
        help="Roll back to previous release on failure.",
        rich_help_panel="Switch Options",
    ),
    search_replace: Optional[bool] = typer.Option(
        None,
        "--search-replace/--no-search-replace",
        help="Run search-and-replace in DB after restore.",
        rich_help_panel="Switch Options",
    ),
    drain_workers: Optional[bool] = typer.Option(
        None,
        "--drain-workers/--no-drain-workers",
        help="Drain workers before restart.",
        rich_help_panel="Switch Options",
    ),
    sync_workers: Optional[bool] = typer.Option(
        None,
        "--sync-workers/--no-sync-workers",
        help="Sync to remote workers after deploy.",
        rich_help_panel="Switch Options",
    ),
):
    """Ship deploy: create release locally → rsync to remote → switch on remote."""
    overrides: dict = {}
    if bench_name is not None:
        overrides["site_name"] = bench_name
    if apps:
        overrides["apps"] = parse_app_option(apps)
    if github_token is not None:
        overrides["github_token"] = github_token
    if uv is not None:
        overrides["uv"] = uv

    switch: dict = {}
    if migrate is not None:
        switch["migrate"] = migrate
    if migrate_timeout is not None:
        switch["migrate_timeout"] = migrate_timeout
    if maintenance_mode is not None:
        switch["maintenance_mode"] = maintenance_mode
    if backups is not None:
        switch["backups"] = backups
    if rollback is not None:
        switch["rollback"] = rollback
    if search_replace is not None:
        switch["search_replace"] = search_replace
    if drain_workers is not None:
        switch["drain_workers"] = drain_workers
    if sync_workers is not None:
        switch["sync_workers"] = sync_workers
    if switch:
        overrides["switch"] = switch

    release: dict = {}
    if releases_retain_limit is not None:
        release["releases_retain_limit"] = releases_retain_limit
    if symlink_subdir_apps is not None:
        release["symlink_subdir_apps"] = symlink_subdir_apps
    if python_version is not None:
        release["python_version"] = python_version
    if node_version is not None:
        release["node_version"] = node_version
    if runner_image is not None:
        release["runner_image"] = runner_image
    if release:
        overrides["release"] = release

    config = load_config(config_path, overrides=overrides or None, create_if_missing=True)
    printer = get_printer()

    if not config.ship:
        typer.echo("Error: config has no [ship] section.", err=True)
        raise typer.Exit(code=1)

    if config_path is None:
        typer.echo("Error: --config is required for ship deploy.", err=True)
        raise typer.Exit(code=1)

    if config.release.mode == "exec":
        typer.echo(
            "Warning: ship mode requires image mode for artifact creation, ignoring config.release.mode = 'exec'",
            err=True,
        )

    image_runner, exec_runner, host_runner = build_runners(config)

    printer.start("Shipping")
    manager = ShipManager(config, image_runner, exec_runner, host_runner, printer)
    manager.deploy(config_path.resolve())
    printer.stop()
    typer.echo("Ship complete.")
