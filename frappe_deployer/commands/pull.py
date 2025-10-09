from pathlib import Path
import time
from typing import Annotated, List, Optional
from frappe_manager.logger.log import richprint
import typer
from frappe_deployer.commands.remote_worker import sync
from frappe_deployer.config.config import Config
from frappe_deployer.deployment_manager import DeploymentManager
from frappe_deployer.helpers import human_readable_time, timing_manager

from frappe_deployer.commands import app, get_config_overrides, parse_apps, validate_cofig_path, validate_db_file_path
from frappe_deployer.remote_worker import is_remote_worker_enabled, link_worker_configs, only_start_workers_compose_services, rsync_workspace, stop_all_compose_services


@app.command(no_args_is_help=True)
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
    migrate_timeout: Annotated[Optional[int], typer.Option(help="Migrate timeout", show_default=False)] = None,
    wait_workers: Annotated[
        Optional[bool],
        typer.Option(help="Whether to enable waiting for workers", show_default=False, rich_help_panel="FM Mode"),
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
        typer.Option(
            "--remote-name", help="Name of the remote to use during cloning (default: upstream)", show_default=False
        ),
    ] = None,
    fc_key: Annotated[
        Optional[str],
        typer.Option("--fc-key", help="Frappe Cloud API key", show_default=False, rich_help_panel="Frappe Cloud"),
    ] = None,
    fc_secret: Annotated[
        Optional[str],
        typer.Option("--fc-secret", help="Frappe Cloud API secret", show_default=False, rich_help_panel="Frappe Cloud"),
    ] = None,
    fc_site_name: Annotated[
        Optional[str],
        typer.Option(
            "--fc-site-name", help="Frappe Cloud Site Name", show_default=False, rich_help_panel="Frappe Cloud"
        ),
    ] = None,
    fc_team_name: Annotated[
        Optional[str],
        typer.Option(
            "--fc-team-name", help="Frappe Cloud Team Name", show_default=False, rich_help_panel="Frappe Cloud"
        ),
    ] = None,
    fc_use_deps: Annotated[
        Optional[bool],
        typer.Option(
            "--fc-use-deps",
            help="Use Frappe Cloud dependencies list i.e python version, node version",
            show_default=False,
            rich_help_panel="Frappe Cloud",
        ),
    ] = None,
    fc_use_db: Annotated[
        Optional[str],
        typer.Option("--fc-use-db", help="Frappe Cloud Site Name", show_default=False, rich_help_panel="Frappe Cloud"),
    ] = None,
    symlink_subdir_apps: Annotated[
        bool,
        typer.Option(
            "--symlink-subdir-apps",
            help="For subdir apps use symlink, useful for local dev.",
            show_default=True,
        ),
    ] = False,
    remote_worker_server_ip: Annotated[
        Optional[str],
        typer.Option("--remote-worker-server-ip", "--rw-ip", help="Remote Worker server IP address or domain name"),
    ] = None,
    remote_worker_sync: Annotated[
        bool,
        typer.Option("--remote-worker-sync", "--rw-sync", help="Toggle to enable remote worker sync."),
    ] = False,
    remote_worker_ssh_user: Annotated[
        Optional[str], typer.Option("--remote-worker-ssh-user", "--rw-user", help="Remote Worker server ssh username")
    ] = None,
    remote_worker_ssh_port: Annotated[
        Optional[int], typer.Option("--remote-worker-ssh-port", "--rw-port", help="Remote Worker server ssh port no.")
    ] = None,
    remote_worker_include_dirs: Annotated[
        Optional[list[str]], typer.Option("--remote-worker-include-dirs", "--rm-dirs", help="Additional directories to sync to the remote worker server during rsync")
    ] = None,
    remote_worker_include_files: Annotated[
        Optional[list[str]], typer.Option("--remote-worker-include-files", "--rm-dirs", help="Additional files to sync to the remote worker server during rsync")
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

    if remote_worker_sync:
        current_locals["sync_workers"] = remote_worker_sync

    if not fc_key:
        current_locals["fc"] = None

    if remote_worker_server_ip:
        current_locals["remote_worker"] = {
            "server_ip": remote_worker_server_ip,
            "ssh_user": remote_worker_ssh_user or "frappe",
            "ssh_port": remote_worker_ssh_port or 22,
            "include_dirs": remote_worker_include_dirs or [],
            "include_files": remote_worker_include_files or [],
        }

    richprint.start("working")

    config: Config = Config.from_toml(config_path, config_content, get_config_overrides(locals=current_locals))

    if len(config.apps) == 0:
        raise RuntimeError("Apps list cannot be empty in [code]pull[/code] command.")

    manager = DeploymentManager(config)
    manager.configure_basic_info()

    with timing_manager(manager.printer, verbose=config.verbose):
        with timing_manager(manager.printer, verbose=config.verbose, task="Create new release"):
            manager.create_new_release()

        with timing_manager(manager.printer, verbose=config.verbose, task="Remote Worker Sync"):
            if config.sync_workers:
                if (not config.remote_worker or not config.remote_worker.server_ip) and is_remote_worker_enabled(site_name):
                    raise RuntimeError(
                        "Remote worker configuration is required. Provide either a in config file or --remote-worker-server-ip option."
                    )

                stop_all_compose_services(manager)
                rsync_workspace(manager)
                link_worker_configs(manager)
                only_start_workers_compose_services(manager)
