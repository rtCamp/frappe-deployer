from enum import Enum
from pathlib import Path
import time
from typing import Annotated, Any, List, Optional, Union
from unittest.mock import patch

from frappe_deployer.config.config import Config
from frappe_deployer.consts import BYPASS_TOKEN, LOG_FILE_NAME, MAINTENANCE_MODE_CONFIG
from frappe_deployer.deployment_manager import DeploymentManager
from frappe_deployer.exceptions import ConfigPathDoesntExist
from frappe_deployer.helpers import human_readable_time
from frappe_deployer.remote_worker import (
    create_worker_site_config,
    enable_remote_worker,
    link_worker_configs,
    only_start_workers_compose_services,
    rsync_workspace,
    stop_all_compose_services,
)
from frappe_manager import (
    CLI_BENCHES_DIRECTORY,
    CLI_SERVICES_DIRECTORY,
    CLI_SERVICES_NGINX_PROXY_DIR,
)
from frappe_manager.logger.log import richprint
import typer

__version__ = "0.10.0"


def version_callback(value: bool):
    if value:
        typer.echo(f"frappe-deployer version: {__version__}")
        raise typer.Exit()


class ModeEnum(str, Enum):
    fm = "fm"
    host = "host"


class CustomLogger:
    def debug(self, msg):
        print(f"Custom debug: {msg}")


patcher = patch("frappe_manager.logger.log.get_logger.__defaults__", (LOG_FILE_NAME.parent, LOG_FILE_NAME.name))
patcher.start()

cli = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")
remote_worker = typer.Typer(help="Remote worker management commands")
cli.add_typer(remote_worker, name="remote-worker")


@cli.callback()
def main(version: Annotated[bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True)] = False):
    """Frappe Deployer CLI tool"""
    if not version:
        typer.echo(f"frappe-deployer version: {__version__}")


def validate_cofig_path(configpath: Optional[Union[str, Path]]):
    if configpath:
        config_path: Path = Path(configpath)
        if not config_path.exists():
            exception = ConfigPathDoesntExist(str(config_path.absolute()))
            richprint.exit(str(exception.message))
        return Path(config_path)


def validate_db_file_path(db_file_path: Optional[Union[str, Path]]):
    if db_file_path:
        if isinstance(db_file_path, str):
            db_file_path = Path(db_file_path)

        if not db_file_path.exists():
            msg = f"The provided db file at {str(db_file_path)} doesn't exists"
            richprint.exit(str(msg))

        return Path(db_file_path)


def parse_apps(apps_list: list[str]):
    apps = []
    for repo_with_branch_name in apps_list:
        app_parts = repo_with_branch_name.split(":")
        app = {"repo": app_parts[0]}

        if len(app_parts) >= 2:
            app["ref"] = app_parts[1]

        if len(app_parts) >= 3:
            app["subdir_path"] = app_parts[2]

        apps.append(app)
    return apps


def get_config_overrides(locals: dict[Any, Any], exclude: list[str] = []):
    return {k: v for k, v in locals.items() if v is not None and k not in exclude}


@cli.command(no_args_is_help=True)
def configure(
    ctx: typer.Context,
    site_name: Annotated[
        Optional[str],
        typer.Argument(help="The name of the site.", show_default=False, metavar="Site Name / Bench Name"),
    ] = None,
    config_path: Annotated[
        Optional[Path], typer.Option(help="TOML config path", callback=validate_cofig_path, show_default=False)
    ] = None,
    backups: Annotated[bool, typer.Option(help="Take backup")] = True,
    mode: Annotated[
        str,
        typer.Option(
            "--mode",
            "-m",
            help="List of apps in the format [underline]org_name/repo_name:branch[/underline]",
            show_default=False,
        ),
    ] = ModeEnum.fm,
):
    current_locals = locals()

    if not config_path:
        current_locals["mode"] = "fm"

    current_locals.update(configure_basic_deployment_config(site_name))

    richprint.start("working")
    config: Config = Config.from_toml(
        config_file_path=config_path, overrides=get_config_overrides(locals=current_locals)
    )
    DeploymentManager.configure(config=config)


@cli.command(no_args_is_help=True)
def pull(
    ctx: typer.Context,
    site_name: Annotated[
        Optional[str],
        typer.Argument(help="The name of the site.", show_default=False, metavar="Site Name / Bench Name"),
    ] = None,
    config_path: Annotated[
        Optional[Path], typer.Option(help="TOML config path", callback=validate_cofig_path, show_default=False)
    ] = None,
    config_content: Annotated[
        Optional[str], typer.Option(help="TOML config string content", show_default=False)
    ] = None,
    apps: Annotated[
        list[str],
        typer.Option(
            "--apps",
            "-a",
            help="List of apps in the format [underline]org_name/repo_name:branch[/underline]",
            callback=parse_apps,
            show_default=False,
        ),
    ] = [],
    github_token: Annotated[
        Optional[str], typer.Option(help="The GitHub personal access token", show_default=False)
    ] = None,
    mode: Annotated[
        Optional[str],
        typer.Option("--mode", "-m", help="Mode of operation, either 'host' or 'fm'.", show_default=False),
    ] = None,
    python_version: Annotated[
        Optional[str],
        typer.Option(
            "--python-version",
            "-p",
            help="Specifiy the python version used to create bench python env. Defaults to whatever currently installed python version on your system.",
            show_default=False,
        ),
    ] = None,
    releases_retain_limit: Annotated[
        Optional[int], typer.Option("--releases-retain-limit", help="Number of releases to retain", show_default=False)
    ] = None,
    remove_remote: Annotated[
        Optional[bool], typer.Option(help="Remove remote after cloning", show_default=False)
    ] = None,
    rollback: Annotated[Optional[bool], typer.Option(help="Enable/Disable rollback", show_default=False)] = None,
    maintenance_mode: Annotated[
        Optional[bool], typer.Option(help="Enable/Disable maintenance mode", show_default=False)
    ] = None,
    maintenance_mode_phases: Annotated[
        Optional[List[str]], typer.Option(help="For which phases maintenance mode will be enabled.", show_default=False)
    ] = None,
    search_replace: Annotated[
        Optional[bool], typer.Option(help="Enable search and replace in database.", show_default=False)
    ] = None,
    run_bench_migrate: Annotated[
        Optional[bool], typer.Option(help="Enable/Disable 'bench migrate' run", show_default=False)
    ] = None,
    migrate_timeout: Annotated[
        Optional[int], typer.Option(help="Migrate timeout", show_default=False)
    ] = None,
    wait_workers: Annotated[
        Optional[bool], typer.Option(help="Whether to enable waiting for workers", show_default=False, rich_help_panel="FM Mode")
    ] = None,
    wait_workers_timeout: Annotated[
        Optional[int], typer.Option(help="Wait workers timeout", show_default=False, rich_help_panel="FM Mode")
    ] = None,
    backups: Annotated[Optional[bool], typer.Option(help="Enable/Disable taking backups")] = None,
    uv: Annotated[
        Optional[bool],
        typer.Option(
            "--uv",
            help="Use [underline]uv[/underline] instead of [underline]pip[/underline] to manage and install packages",
            show_default=False,
        ),
    ] = None,
    verbose: Annotated[
        Optional[bool], typer.Option("--verbose", "-v", help="Enable verbose output", show_default=False)
    ] = None,
    host_bench_path: Annotated[
        Optional[Path],
        typer.Option(
            help="Specify the path to the bench directory",
            show_default=False,
            rich_help_panel="Host Mode",
        ),
    ] = None,
    fm_restore_db_from_site: Annotated[
        Optional[str],
        typer.Option(
            help="Specify the site name to import the database from.", show_default=False, rich_help_panel="FM Mode"
        ),
    ] = None,
    configure: Annotated[
        Optional[bool], typer.Option(help="If not configure then configure and then pull.", show_default=False)
    ] = None,
    restore_db_file_path: Annotated[
        Optional[Path], typer.Option(help="Restore db file path", callback=validate_db_file_path, show_default=False)
    ] = None,
    remote_name: Annotated[
        Optional[str], 
        typer.Option("--remote-name", help="Name of the remote to use during cloning (default: upstream)", show_default=False)
    ] = None,
    fc_key: Annotated[
        Optional[str],
        typer.Option("--fc-key", help="Frappe Cloud API key", show_default=False, rich_help_panel="Frappe Cloud")
    ] = None,
    fc_secret: Annotated[
        Optional[str],
        typer.Option("--fc-secret", help="Frappe Cloud API secret", show_default=False, rich_help_panel ="Frappe Cloud")
    ] = None,
    fc_site_name: Annotated[
        Optional[str],
        typer.Option("--fc-site-name", help="Frappe Cloud Site Name", show_default=False, rich_help_panel="Frappe Cloud")
    ] = None,
    fc_team_name: Annotated[
        Optional[str],
        typer.Option("--fc-team-name", help="Frappe Cloud Team Name", show_default=False, rich_help_panel="Frappe Cloud")
    ] = None,
    fc_use_deps: Annotated[
        Optional[bool],
        typer.Option("--fc-use-deps", help="Use Frappe Cloud dependencies list i.e python version, node version", show_default=False, rich_help_panel ="Frappe Cloud")
    ] = None,
    fc_use_db: Annotated[
        Optional[str],
        typer.Option("--fc-use-db", help="Frappe Cloud Site Name", show_default=False, rich_help_panel="Frappe Cloud")
    ] = None,
):
    """
    Pulls the current set of frappe apps and setup new release based on provided config file/flags.

    The config file that you pass will set the default initial configuration.

    Flags are provided to override/add configurations present in config.
    """
    current_locals = locals()

    if host_bench_path:
        current_locals["host"] = {"bench_path": str(host_bench_path.absolute())}

    if fm_restore_db_from_site:
        current_locals["fm"] = {"restore_db_from_site": fm_restore_db_from_site}

    richprint.start("working")
    config: Config = Config.from_toml(config_path, config_content, get_config_overrides(locals=current_locals))

    if len(config.apps) == 0:
        raise RuntimeError("Apps list cannot be empty in [code]pull[/code] command.")

    manager = DeploymentManager(config)
    manager.configure_basic_info()

    total_start_time = time.time()

    manager.create_new_release()

    if config.verbose:
        total_end_time = time.time()
        total_elapsed_time = total_end_time - total_start_time
        manager.printer.print(
            f"Total Time Taken: [bold yellow]{human_readable_time(total_elapsed_time)}[/bold yellow]",
            emoji_code=":robot_face:",
        )


@cli.command(no_args_is_help=True)
def enable_maintenance(
    ctx: typer.Context,
    site_name: Annotated[
        Optional[str],
        typer.Argument(help="The name of the site.", show_default=False, metavar="Site Name / Bench Name"),
    ] = None,
):
    richprint.start("working")

    # check if site exists
    site_config_path: Path = CLI_BENCHES_DIRECTORY / f"{site_name}"

    if not site_config_path.exists():
        richprint.exit(f"Site {site_name} does not exist")

    try:
        # Write maintenance config
        vhostd_config_path: Path = CLI_SERVICES_NGINX_PROXY_DIR / "vhostd" / f"{site_name}_location"
        vhostd_config_path.write_text(MAINTENANCE_MODE_CONFIG.format(BYPASS_TOKEN=BYPASS_TOKEN))

        # Reload nginx to apply changes
        from subprocess import run

        run(
            [
                "docker",
                "compose",
                "-f",
                str(CLI_SERVICES_DIRECTORY / "docker-compose.yml"),
                "restart",
                "global-nginx-proxy",
            ]
        )

        richprint.print(f"Maintenance mode enabled for site {site_name}")
        richprint.print(f"Developer bypass URL: [link]http://{site_name}/{BYPASS_TOKEN}/[/link]")
    except Exception as e:
        richprint.exit(f"Failed to enable maintenance mode: {str(e)}")


@cli.command(no_args_is_help=True)
def disable_maintenance(
    ctx: typer.Context,
    site_name: Annotated[
        Optional[str],
        typer.Argument(help="The name of the site.", show_default=False, metavar="Site Name / Bench Name"),
    ] = None,
):
    richprint.start("working")

    # check if site exists
    site_config_path: Path = CLI_BENCHES_DIRECTORY / f"{site_name}"

    if not site_config_path.exists():
        richprint.exit(f"Site {site_name} does not exist")

    try:
        # Remove maintenance config if it exists
        vhostd_config_path: Path = CLI_SERVICES_NGINX_PROXY_DIR / "vhostd" / f"{site_name}_location"
        if vhostd_config_path.exists():
            vhostd_config_path.unlink()

        # Reload nginx to apply changes
        from subprocess import run

        run(
            [
                "docker",
                "compose",
                "-f",
                str(CLI_SERVICES_DIRECTORY / "docker-compose.yml"),
                "restart",
                "global-nginx-proxy",
            ]
        )

        richprint.print(f"Maintenance mode disabled for site {site_name}")
    except Exception as e:
        richprint.exit(f"Failed to disable maintenance mode: {str(e)}")


@cli.command(no_args_is_help=True)
def search_replace(
    ctx: typer.Context,
    site_name: Annotated[str, typer.Argument(help="The name of the site.")],
    search: Annotated[str, typer.Argument(help="Text to search for")],
    replace: Annotated[str, typer.Argument(help="Text to replace with")],
    dry_run: Annotated[bool, typer.Option(help="Show what would be changed without making changes")] = False,
):
    """
    Search and replace text across all text fields in the Frappe database
    """
    richprint.start("working")

    # Check if site exists
    site_config_path: Path = CLI_BENCHES_DIRECTORY / f"{site_name}"

    if not site_config_path.exists():
        richprint.exit(f"Site {site_name} does not exist")

    try:
        # Create minimal config for DeploymentManager
        from frappe_deployer.config.config import Config

        config = Config(site_name=site_name, bench_path=site_config_path / "workspace/frappe-bench", apps=[], mode="fm")
        manager = DeploymentManager(config)
        manager.configure_basic_info()

        # Use the DeploymentManager's search_and_replace_in_database method
        manager.search_and_replace_in_database(
            search=search, replace=replace, dry_run=dry_run, verbose=manager.config.verbose
        )
    except Exception as e:
        richprint.warning(f"Failed to perform search and replace: {str(e)}")


@cli.command()
def cleanup(
    ctx: typer.Context,
    site_name: Annotated[
        Optional[str],
        typer.Argument(help="The name of the site.", show_default=False, metavar="Site Name / Bench Name"),
    ] = None,
    config_path: Annotated[
        Optional[Path], typer.Option("--config-path","-c",help="TOML config path", callback=validate_cofig_path, show_default=False)
    ] = None,
    backup_retain_limit: Annotated[
        int,
        typer.Option(
            "--backup-retain-limit",
            "-b",
            help="Number of backup directories to retain",
            show_default=True
        )
    ] = 0,
    release_retain_limit: Annotated[
        int,
        typer.Option(
            "--release-retain-limit",
            "-r",
            help="Number of release directories to retain (current release is always kept)",
            show_default=True
        )
    ] = 0,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes", "-y",
            help="Auto-approve all cleanup operations without prompting",
            show_default=True
        )
    ] = False,
    show_sizes: Annotated[
        bool,
        typer.Option(
            "--show-sizes", "-s", 
            help="Calculate and show directory sizes (may be slow for large directories)",
            show_default=True
        )
    ] = True,
    verbose: Annotated[
        Optional[bool], 
        typer.Option("--verbose", "-v", help="Enable verbose output", show_default=False)
    ] = None,
):
    """
    Cleanup deployment backups and releases.
    - Retains specified number of recent backup directories
    - Optionally retains specified number of release directories
    Will sort by timestamp in name before determining which to keep.
    Current release is always preserved.
    """
    current_locals = locals()

    if not config_path:
        current_locals["mode"] = "fm"

    current_locals.update(configure_basic_deployment_config(site_name))

    richprint.start("working")
    config = Config.from_toml(
        config_file_path=config_path,
        overrides=get_config_overrides(locals=current_locals)
    )

    manager = DeploymentManager(config)
    manager.cleanup_workspace_cache(backup_retain_limit, release_retain_limit, auto_approve=yes, show_sizes=show_sizes)


@remote_worker.command()
def enable(
    site_name: Annotated[str, typer.Argument(help="The name of the site")],
    config_path: Annotated[
        Optional[Path], typer.Option(help="TOML config path", callback=validate_cofig_path, show_default=False)
    ] = None,
    server: Annotated[
        Optional[str], typer.Option("--server", "-s", help="Remote server IP address or domain name")
    ] = None,
    ssh_user: Annotated[
        Optional[str], typer.Option("--ssh-user", "-u", help="SSH username for the remote server")
    ] = None,
    ssh_port: Annotated[Optional[int], typer.Option("--ssh-port", "-p", help="SSH port number")] = None,
    verbose: Annotated[
        Optional[bool], typer.Option("--verbose", "-v", help="Enable verbose output", show_default=False)
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force", help="Force recreate common_site_config.json and site_config.json if exists.", show_default=False
        ),
    ] = False,
):
    """
    Sync workspace to remote worker server.

    Only FM mode is supported as of now.
    """

    current_locals = locals()

    # Create remote worker config if server details provided via CLI
    if server:
        current_locals["remote_worker"] = {
            "server": server,
            "ssh_user": ssh_user or "frappe",
            "ssh_port": ssh_port or 22,
            "include_dirs": include_dirs or [],
            "include_files": include_files or [],
        }

    if not config_path:
        current_locals["mode"] = "fm"

    current_locals.update(configure_basic_deployment_config(site_name))

    richprint.start("working")
    config = Config.from_toml(
        config_file_path=config_path, overrides=get_config_overrides(locals=current_locals, exclude=["force"])
    )

    if not config.remote_worker or not config.remote_worker.server:
        raise RuntimeError("Remote worker configuration is required. Provide either a config file or --server option.")

    deployment_manager = DeploymentManager(config)

    enable_remote_worker(site_name)
    create_worker_site_config(deployment_manager=deployment_manager, force=force)


@remote_worker.command()
def sync(
    site_name: Annotated[str, typer.Argument(help="The name of the site")],
    config_path: Annotated[
        Optional[Path], typer.Option(help="TOML config path", callback=validate_cofig_path, show_default=False)
    ] = None,
    server: Annotated[
        Optional[str], typer.Option("--server", "-s", help="Remote server IP address or domain name")
    ] = None,
    ssh_user: Annotated[
        Optional[str], typer.Option("--ssh-user", "-u", help="SSH username for the remote server")
    ] = None,
    ssh_port: Annotated[Optional[int], typer.Option("--ssh-port", "-p", help="SSH port number")] = None,
    include_dirs: Annotated[
        Optional[list[str]], typer.Option("--include-dir", "-d", help="Additional directories to sync")
    ] = None,
    include_files: Annotated[
        Optional[list[str]], typer.Option("--include-file", "-f", help="Additional files to sync")
    ] = None,
    verbose: Annotated[
        Optional[bool], typer.Option("--verbose", "-v", help="Enable verbose output", show_default=False)
    ] = None,
):
    """
    Sync workspace to remote worker server.

    Only FM mode is supported as of now.
    """

    current_locals = locals()

    # Create remote worker config if server details provided via CLI
    if server:
        current_locals["remote_worker"] = {
            "server": server,
            "ssh_user": ssh_user or "frappe",
            "ssh_port": ssh_port or 22,
            "include_dirs": include_dirs or [],
            "include_files": include_files or [],
        }

    if not config_path:
        current_locals["mode"] = "fm"

    current_locals.update(configure_basic_deployment_config(site_name))

    richprint.start("working")

    config = Config.from_toml(config_file_path=config_path, overrides=get_config_overrides(locals=current_locals))

    if not config.remote_worker or not config.remote_worker.server:
        raise RuntimeError("Remote worker configuration is required. Provide either a config file or --server option.")

    deployment_manager = DeploymentManager(config)
    deployment_manager.printer.print(f"Starting sync to remote worker at {server}")

    stop_all_compose_services(deployment_manager)
    rsync_workspace(deployment_manager=deployment_manager)
    link_worker_configs(deployment_manager)
    only_start_workers_compose_services(deployment_manager)


def configure_basic_deployment_config(site_name: str) -> dict:
    """Create a minimal deployment manager for syncing operations.

    Args:
        site_name (str): Name of the site
        source_path (Path): Source path for the bench

    Returns:
        DeploymentManager: Minimal deployment manager instance
    """

    data: dict[str, Any] = {}
    data["site_name"] = site_name
    data["bench_path"] = str(CLI_BENCHES_DIRECTORY / f"{site_name}/frappe-bench")
    data["apps"] = []

    return data

@cli.command(no_args_is_help=True)
def clone(
    ctx: typer.Context,
    site_name: Annotated[str, typer.Argument(help="The name of the site.")],
    apps: Annotated[
        list[str],
        typer.Option(
            "--apps",
            "-a",
            help="List of apps in the format [underline]org_name/repo_name:branch:subdir_path[/underline]",
            callback=parse_apps,
            show_default=False,
        ),
    ] = [],
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite",
            "-o",
            help="Overwrite existing app directories if they exist.",
            show_default=True,
        ),
    ] = False,
    backup: Annotated[
        bool,
        typer.Option(
            "--backup",
            "-b",
            help="Backup overwritten app directories before replacing.",
            show_default=True,
        ),
    ] = True,
):
    """
    Search and replace text across all text fields in the Frappe database
    """
    richprint.start("working")

    # Check if site exists
    site_config_path: Path = CLI_BENCHES_DIRECTORY / f"{site_name}"

    if not site_config_path.exists():
        richprint.exit(f"Site {site_name} does not exist")

    try:
        from frappe_deployer.config.config import Config
        config = Config(site_name=site_name, bench_path=site_config_path / "workspace/frappe-bench", apps=apps, mode="fm")
        manager = DeploymentManager(config)
        manager.clone_apps(manager.current, overwrite=overwrite, backup=backup)
    except Exception as e:
        richprint.warning(f"Failed : {str(e)}")
