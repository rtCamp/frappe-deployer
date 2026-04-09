from pathlib import Path
from typing import List, Optional

import typer

from fmd.commands._utils import build_runners, get_printer, load_config, parse_app_option
from fmd.managers.pull import PullManager


def pull(
    bench_name: Optional[str] = typer.Argument(None, help="Bench name (required when no config file is provided)."),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to site config TOML file."),
    apps: List[str] = typer.Option(
        [], "--app", "-a", help="App in format org/repo:ref[:subdir_path]. Repeatable.", show_default=False
    ),
    github_token: Optional[str] = typer.Option(
        None, "--github-token", help="GitHub personal access token.", show_default=False
    ),
    python_version: Optional[str] = typer.Option(
        None, "--python-version", "-p", help="Python version for venv.", show_default=False
    ),
    node_version: Optional[str] = typer.Option(
        None, "--node-version", "-n", help="Node.js version to install via fnm.", show_default=False
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
    fc_key: Optional[str] = typer.Option(
        None, "--fc-key", help="Frappe Cloud API key.", show_default=False, rich_help_panel="Frappe Cloud"
    ),
    fc_secret: Optional[str] = typer.Option(
        None, "--fc-secret", help="Frappe Cloud API secret.", show_default=False, rich_help_panel="Frappe Cloud"
    ),
    fc_site: Optional[str] = typer.Option(
        None, "--fc-site", help="Frappe Cloud site name.", show_default=False, rich_help_panel="Frappe Cloud"
    ),
    fc_team: Optional[str] = typer.Option(
        None, "--fc-team", help="Frappe Cloud team name.", show_default=False, rich_help_panel="Frappe Cloud"
    ),
    fc_use_deps: Optional[bool] = typer.Option(
        None,
        "--fc-use-deps/--no-fc-use-deps",
        help="Use FC dependencies (python version etc).",
        rich_help_panel="Frappe Cloud",
    ),
    fc_use_db: Optional[bool] = typer.Option(
        None,
        "--fc-use-db/--no-fc-use-db",
        help="Restore from latest FC DB backup on switch.",
        rich_help_panel="Frappe Cloud",
    ),
    fc_use_apps: Optional[bool] = typer.Option(
        None,
        "--fc-use-apps/--no-fc-use-apps",
        help="Merge FC app list into config apps.",
        rich_help_panel="Frappe Cloud",
    ),
    rw_server: Optional[str] = typer.Option(
        None,
        "--rw-server",
        "--remote-worker-server-ip",
        help="Remote worker server IP/domain.",
        show_default=False,
        rich_help_panel="Remote Worker",
    ),
    rw_user: Optional[str] = typer.Option(
        None,
        "--rw-user",
        "--remote-worker-ssh-user",
        help="Remote worker SSH user.",
        show_default=False,
        rich_help_panel="Remote Worker",
    ),
    rw_port: Optional[int] = typer.Option(
        None,
        "--rw-port",
        "--remote-worker-ssh-port",
        help="Remote worker SSH port.",
        show_default=False,
        rich_help_panel="Remote Worker",
    ),
):
    """Full deploy: configure (if needed) → create release → switch."""
    overrides: dict = {}
    if bench_name is not None:
        overrides["site_name"] = bench_name
    if apps:
        overrides["apps"] = parse_app_option(apps)
    if github_token is not None:
        overrides["github_token"] = github_token
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
    if python_version is not None:
        release["python_version"] = python_version
    if node_version is not None:
        release["node_version"] = node_version
    if release:
        overrides["release"] = release

    if fc_key or fc_secret or fc_site or fc_team:
        fc: dict = {}
        if fc_key:
            fc["api_key"] = fc_key
        if fc_secret:
            fc["api_secret"] = fc_secret
        if fc_site:
            fc["site_name"] = fc_site
        if fc_team:
            fc["team_name"] = fc_team
        if fc_use_deps is not None:
            fc["use_deps"] = fc_use_deps
        if fc_use_db is not None:
            fc["use_db"] = fc_use_db
        if fc_use_apps is not None:
            fc["use_apps"] = fc_use_apps
        overrides["fc"] = fc

    if rw_server:
        rw: dict = {"server_ip": rw_server}
        if rw_user:
            rw["ssh_user"] = rw_user
        if rw_port:
            rw["ssh_port"] = rw_port
        overrides["remote_worker"] = rw

    config = load_config(config_path, overrides=overrides or None, create_if_missing=True)
    printer = get_printer()
    image_runner, exec_runner, host_runner = build_runners(config)
    printer.start("Deploying")
    manager = PullManager(config, image_runner, exec_runner, host_runner, printer)
    manager.deploy()
    printer.stop()
    typer.echo("Deploy complete.")
