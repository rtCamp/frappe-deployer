from pathlib import Path
from typing import Annotated, Optional

from frappe_deployer.config.config import Config
from frappe_deployer.deployment_manager import DeploymentManager
from frappe_deployer.remote_worker import (
    create_worker_site_config,
    enable_remote_worker,
    is_remote_worker_enabled,
    link_worker_configs,
    only_start_workers_compose_services,
    rsync_workspace,
    stop_all_compose_services,
)
from frappe_manager.logger.log import richprint
import typer
from frappe_deployer.commands import app, configure_basic_deployment_config, get_config_overrides, validate_cofig_path

remote_worker = typer.Typer(help="Remote worker management commands")
app.add_typer(remote_worker, name="remote-worker")

@remote_worker.command()
def enable(
    site_name: Annotated[str, typer.Argument(help="The name of the site")],
    config_path: Annotated[
        Optional[Path], typer.Option(help="TOML config path", callback=validate_cofig_path, show_default=False)
    ] = None,
    server: Annotated[
        Optional[str], typer.Option("--server-ip", "-s", help="Remote server IP address or domain name")
    ] = None,
    ssh_user: Annotated[
        Optional[str], typer.Option("--ssh-user", "-u", help="SSH username for the remote server")
    ] = None,
    ssh_port: Annotated[Optional[int], typer.Option("--ssh-port", "-p", help="SSH port number")] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force", help="Force recreate common_site_config.json and site_config.json if exists.", show_default=False
        ),
    ] = False,
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
            "server_ip": server,
            "ssh_user": ssh_user or "frappe",
            "ssh_port": ssh_port or 22,
            # "include_dirs": include_dirs or [],
            # "include_files": include_files or [],
        }

    if not config_path:
        current_locals["mode"] = "fm"

    current_locals.update(configure_basic_deployment_config(site_name))

    richprint.start("working")

    config = Config.from_toml(
        config_file_path=config_path, overrides=get_config_overrides(locals=current_locals, exclude=["force"])
    )

    if not config.remote_worker or not config.remote_worker.server_ip:
        raise RuntimeError("Remote worker configuration is required. Provide either a config file or --server option.")

    deployment_manager = DeploymentManager(config)

    if is_remote_worker_enabled(site_name):
        richprint.print("Remote worker already enabled.")
        return

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
            "server_ip": server,
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

    if not config.remote_worker or not config.remote_worker.server_ip:
        raise RuntimeError("Remote worker configuration is required. Provide either a config file or --server option.")

    deployment_manager = DeploymentManager(config)
    deployment_manager.printer.print(f"Starting sync to remote worker at {server}")

    stop_all_compose_services(deployment_manager)
    rsync_workspace(deployment_manager=deployment_manager)
    link_worker_configs(deployment_manager)
    only_start_workers_compose_services(deployment_manager)
