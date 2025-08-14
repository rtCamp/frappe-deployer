from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Optional, Union
from frappe_deployer import version_callback
from frappe_deployer.exceptions import ConfigPathDoesntExist
from frappe_manager import CLI_BENCHES_DIRECTORY
from frappe_manager.logger.log import richprint
import typer

class ModeEnum(str, Enum):
    fm = "fm"
    host = "host"

COMMAND_MODULES = ["callback",'pull', 'cleanup', 'clone', 'maintenance', 'remote_worker', "search_replace", "info"]

app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")
# remote_worker = typer.Typer(help="Remote worker management commands")
# app.add_typer(remote_worker, name="remote-worker")


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

def load_commands():
    """
    Dynamically load all command modules and register them with the app.
    This is done after app initialization to avoid circular imports.
    """
    for module_name in COMMAND_MODULES:
        __import__(f'frappe_deployer.commands.{module_name}')

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

# version_callback(show=True)
load_commands()
