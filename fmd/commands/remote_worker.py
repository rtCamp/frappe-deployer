from pathlib import Path
from typing import Optional

import typer
from typer_examples import example, install

from fmd.commands._utils import get_printer, load_config
from fmd.managers.remote_worker import RemoteWorkerManager

app = typer.Typer(rich_markup_mode="rich", invoke_without_command=True)
install(app)


@app.callback()
def remote_worker_callback(ctx: typer.Context):
    """Enable and sync remote Frappe workers."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@example(
    "Enable from config file",
    "--config {config_path}",
    detail="Reads bench name and remote worker settings from config, exposes DB/Redis ports and writes worker site configs.",
    config_path="./site.toml",
)
@example(
    "Enable with bench name",
    "{bench_name} --rw-server {rw_server}",
    detail="Enables remote worker for the specified bench, pointing at the given remote server IP.",
    bench_name="mybench",
    rw_server="10.0.0.5",
)
@app.command()
def enable(
    bench_name: Optional[str] = typer.Argument(None, help="Bench name (required when no config file is provided)."),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to site config TOML file."),
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
    overrides: dict = {}
    if bench_name is not None:
        overrides["site_name"] = bench_name
    remote_worker: dict = {}
    if rw_server is not None:
        remote_worker["server_ip"] = rw_server
    if rw_user is not None:
        remote_worker["ssh_user"] = rw_user
    if rw_port is not None:
        remote_worker["ssh_port"] = rw_port
    if remote_worker:
        overrides["remote_worker"] = remote_worker
    config = load_config(config_path, overrides=overrides if overrides else None)
    printer = get_printer()
    printer.start("Working")
    manager = RemoteWorkerManager(config, printer)
    manager.enable(force=force)
    printer.stop()


@example(
    "Sync from config file",
    "--config {config_path}",
    detail="Reads bench name and remote worker settings from config and syncs the workspace to the remote server.",
    config_path="./site.toml",
)
@example(
    "Sync with bench name",
    "{bench_name} --rw-server {rw_server}",
    detail="Syncs the workspace for the specified bench to the remote worker server.",
    bench_name="mybench",
    rw_server="10.0.0.5",
)
@app.command()
def sync(
    bench_name: Optional[str] = typer.Argument(None, help="Bench name (required when no config file is provided)."),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to site config TOML file."),
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
    overrides: dict = {}
    if bench_name is not None:
        overrides["site_name"] = bench_name
    remote_worker: dict = {}
    if rw_server is not None:
        remote_worker["server_ip"] = rw_server
    if rw_user is not None:
        remote_worker["ssh_user"] = rw_user
    if rw_port is not None:
        remote_worker["ssh_port"] = rw_port
    if remote_worker:
        overrides["remote_worker"] = remote_worker
    config = load_config(config_path, overrides=overrides if overrides else None)
    printer = get_printer()
    printer.start("Working")
    manager = RemoteWorkerManager(config, printer)
    manager.sync()
    printer.stop()
