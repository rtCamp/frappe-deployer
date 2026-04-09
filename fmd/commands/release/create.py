from pathlib import Path
from typing import List, Optional

import typer

from fmd.commands._utils import build_runners, get_printer, is_exec_mode_available, load_config, parse_app_option
from fmd.managers.release import ReleaseManager


def create(
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
    backups: Optional[bool] = typer.Option(None, "--backups/--no-backups", help="Take DB backup before create."),
    symlink_subdir_apps: Optional[bool] = typer.Option(
        None, "--symlink-subdir-apps/--no-symlink-subdir-apps", help="Symlink all subdir apps."
    ),
    releases_retain_limit: Optional[int] = typer.Option(
        None, "--releases-retain-limit", help="Number of releases to retain.", show_default=False
    ),
    runner_image: Optional[str] = typer.Option(
        None,
        "--runner-image",
        help="Docker image to use for release creation. Overrides auto-detection.",
        show_default=False,
    ),
    mode: Optional[str] = typer.Option(
        None,
        "--mode",
        help="Runner mode: 'image' (docker run) or 'exec' (docker compose exec). Auto-detected from config if not set.",
        show_default=False,
    ),
    build_dir: Optional[Path] = typer.Option(
        None,
        "--build-dir",
        help="Base directory where the release folder is created. Activates image mode. Defaults to workspace/.",
        show_default=False,
    ),
):
    """Create a new release: clone apps, build assets, no live bench changes."""
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
    if backups is not None:
        deploy["backups"] = backups
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
    if runner_image is not None:
        release["runner_image"] = runner_image
    if release:
        overrides["release"] = release

    config = load_config(config_path, overrides=overrides or None, create_if_missing=True)
    printer = get_printer()
    image_runner, exec_runner, host_runner = build_runners(config)

    if build_dir is not None:
        effective_mode = "image"
    else:
        effective_mode = mode or ("image" if config.ship else "exec")

        if effective_mode == "exec" and not is_exec_mode_available(config.workspace_root):
            printer.warning("Exec mode unavailable (frappe service not running), falling back to image mode")
            effective_mode = "image"

    if effective_mode not in ("image", "exec"):
        typer.echo(f"Error: --mode must be 'image' or 'exec', got '{effective_mode}'.", err=True)
        raise typer.Exit(code=1)

    if mode == "exec" and build_dir is not None:
        typer.echo("Error: --build-dir automatically activates image mode, cannot use with --mode exec.", err=True)
        raise typer.Exit(code=1)

    release_image_runner = image_runner if effective_mode == "image" else exec_runner

    printer.start("Creating release")
    manager = ReleaseManager(config, release_image_runner, exec_runner, host_runner, printer)
    release_name = manager.create(build_dir=build_dir)
    printer.stop()
    release_path = (build_dir.resolve() / release_name) if build_dir else release_name
    typer.echo(f"Release created: {release_path}")
