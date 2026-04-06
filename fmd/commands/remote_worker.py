from pathlib import Path
from typing import Optional

import typer

from fmd.commands._utils import get_printer, load_config
from fmd.managers.remote_worker import RemoteWorkerManager

app = typer.Typer()


@app.command()
def enable(
    config_path: Path = typer.Argument(..., help="Path to site config TOML file."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing worker configs if they exist."),
    rw_server: Optional[str] = typer.Option(
        None,
        "--rw-server",
        "--remote-worker-server-ip",
        help="Remote worker server IP/domain.",
        rich_help_panel="Remote Worker",
    ),
    rw_user: Optional[str] = typer.Option(
        None, "--rw-user", "--remote-worker-ssh-user", help="Remote worker SSH user.", rich_help_panel="Remote Worker"
    ),
    rw_port: Optional[int] = typer.Option(
        None, "--rw-port", "--remote-worker-ssh-port", help="Remote worker SSH port.", rich_help_panel="Remote Worker"
    ),
):
    """Enable remote worker: expose DB + Redis ports, create worker site configs."""
    remote_worker: dict = {}
    if rw_server is not None:
        remote_worker["server_ip"] = rw_server
    if rw_user is not None:
        remote_worker["ssh_user"] = rw_user
    if rw_port is not None:
        remote_worker["ssh_port"] = rw_port
    overrides = {"remote_worker": remote_worker} if remote_worker else None
    config = load_config(config_path, overrides=overrides)
    printer = get_printer()
    printer.start("Working")
    manager = RemoteWorkerManager(config, printer)
    manager.enable(force=force)
    printer.stop()


@app.command()
def sync(
    config_path: Path = typer.Argument(..., help="Path to site config TOML file."),
    rw_server: Optional[str] = typer.Option(
        None,
        "--rw-server",
        "--remote-worker-server-ip",
        help="Remote worker server IP/domain.",
        rich_help_panel="Remote Worker",
    ),
    rw_user: Optional[str] = typer.Option(
        None, "--rw-user", "--remote-worker-ssh-user", help="Remote worker SSH user.", rich_help_panel="Remote Worker"
    ),
    rw_port: Optional[int] = typer.Option(
        None, "--rw-port", "--remote-worker-ssh-port", help="Remote worker SSH port.", rich_help_panel="Remote Worker"
    ),
):
    """Sync workspace to remote worker server."""
    remote_worker: dict = {}
    if rw_server is not None:
        remote_worker["server_ip"] = rw_server
    if rw_user is not None:
        remote_worker["ssh_user"] = rw_user
    if rw_port is not None:
        remote_worker["ssh_port"] = rw_port
    overrides = {"remote_worker": remote_worker} if remote_worker else None
    config = load_config(config_path, overrides=overrides)
    printer = get_printer()
    printer.start("Working")
    manager = RemoteWorkerManager(config, printer)
    manager.sync()
    printer.stop()
