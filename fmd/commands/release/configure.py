from pathlib import Path
from typing import List, Optional

import typer

from fmd.commands._utils import build_runners, get_printer, load_config, parse_app_option
from fmd.managers.release import ReleaseManager


def configure(
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
    backups: Optional[bool] = typer.Option(None, "--backups/--no-backups", help="Take backup before configure."),
    symlink_subdir_apps: Optional[bool] = typer.Option(
        None, "--symlink-subdir-apps/--no-symlink-subdir-apps", help="Symlink all subdir apps."
    ),
):
    """One-time setup: converts a plain bench into a versioned release structure."""
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
    if backups is not None:
        deploy["backups"] = backups
    if deploy:
        overrides["deploy"] = deploy

    release: dict = {}
    if symlink_subdir_apps is not None:
        release["symlink_subdir_apps"] = symlink_subdir_apps
    if release:
        overrides["release"] = release

    config = load_config(config_path, overrides=overrides or None, create_if_missing=True)
    printer = get_printer()
    image_runner, exec_runner, host_runner = build_runners(config)
    printer.start("Configuring")
    manager = ReleaseManager(config, image_runner, exec_runner, host_runner, printer)
    manager.configure()
    printer.stop()
    typer.echo("Configure complete.")
