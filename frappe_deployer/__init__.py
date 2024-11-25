from enum import Enum
import toml
import re
import time
from pathlib import Path
from typing import Annotated, Any, Literal, Optional, Union
from frappe_manager.logger.log import richprint
import typer

from frappe_deployer.config.config import Config
from frappe_deployer.consts import LOG_FILE_NAME
from frappe_deployer.deployment_manager import DeploymentManager
from frappe_deployer.exceptions import ConfigPathDoesntExist
from unittest.mock import patch

from frappe_deployer.helpers import human_readable_time

class ModeEnum(str, Enum):
    fm = 'fm'
    host = 'host'

class CustomLogger:
    def debug(self, msg):
        print(f"Custom debug: {msg}")


patcher = patch('frappe_manager.logger.log.get_logger.__defaults__', (LOG_FILE_NAME.parent, LOG_FILE_NAME.name))
patcher.start()

cli = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")

def validate_cofig_path(configpath: Optional[Union[str,Path]]):
    if configpath:
        config_path: Path = Path(configpath)
        if not config_path.exists():
            exception = ConfigPathDoesntExist(str(config_path.absolute()))
            richprint.exit(str(exception.message))
        return Path(config_path)


def validate_db_file_path(db_file_path: Optional[Union[str,Path]]):
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
        app_parts = repo_with_branch_name.split(':')
        app = {'repo': app_parts[0]}
        if len(app_parts) >=2:
            app['ref'] = app_parts[1]
        apps.append(app)
    return apps

def get_config_overrides(locals: dict[Any,Any], exclude: list[str] = []):
    return {k: v for k, v in locals.items() if v is not None and k not in exclude}

@cli.command(no_args_is_help=True)
def configure(
    ctx: typer.Context,
    site_name: Annotated[Optional[str], typer.Argument(help='The name of the site.', show_default=False,metavar='Site Name / Bench Name')] = None,
    config_path: Annotated[Optional[Path], typer.Option(help='TOML config path', callback=validate_cofig_path,show_default=False)] = None,
    backups: Annotated[bool, typer.Option(help="Take backup")] = True,
    mode: Annotated[str, typer.Option('--mode','-m', help="List of apps in the format [underline]org_name/repo_name:branch[/underline]", show_default=False)] = ModeEnum.fm,
):
    current_locals = locals()
    richprint.start('working')
    config: Config = Config.from_toml(config_path, get_config_overrides(locals=current_locals))
    DeploymentManager.configure(config=config)

@cli.command(no_args_is_help=True)
def pull(
    ctx: typer.Context,
    site_name: Annotated[Optional[str], typer.Argument(help='The name of the site.', show_default=False,metavar='Site Name / Bench Name')] = None,
    config_path: Annotated[Optional[Path], typer.Option(help='TOML config path', callback=validate_cofig_path,show_default=False)] = None,
    config_content: Annotated[Optional[str], typer.Option(help='TOML config string content', show_default=False)] = None,
    apps: Annotated[list[str] , typer.Option('--apps','-a', help="List of apps in the format [underline]org_name/repo_name:branch[/underline]", callback=parse_apps, show_default=False)] = [],
    github_token: Annotated[Optional[str], typer.Option(help="The GitHub personal access token",show_default=False)] = None,
    mode: Annotated[Optional[str], typer.Option('--mode','-m', help="Mode of operation, either 'host' or 'fm'.", show_default=False)] = None,
    python_version: Annotated[Optional[str], typer.Option('--python-version','-p', help="Specifiy the python version used to create bench python env. Defaults to whatever currently installed python version on your system.", show_default=False)] = None,
    releases_retain_limit: Annotated[Optional[int] , typer.Option('--releases-retain-limit', help="Number of releases to retain", show_default=False)] = None,
    remove_remote: Annotated[Optional[bool] , typer.Option(help="Remove remote after cloning",show_default=False)] = None,
    rollback: Annotated[Optional[bool] , typer.Option(help="Enable/Disable rollback",show_default=False)] = None,
    maintenance_mode: Annotated[Optional[bool] , typer.Option(help="Enable/Disable maintenance mode",show_default=False)] = None,
    run_bench_migrate: Annotated[Optional[bool] , typer.Option(help="Enable/Disable 'bench migrate' run",show_default=False)] = None,
    backups: Annotated[Optional[bool], typer.Option(help="Enable/Disable taking backups")] = None,
    uv: Annotated[Optional[bool] , typer.Option('--uv',help="Use [underline]uv[/underline] instead of [underline]pip[/underline] to manage and install packages", show_default=False)] = None,
    verbose: Annotated[Optional[bool] , typer.Option('--verbose','-v',help="Enable verbose output", show_default=False)] = None,
    host_bench_path: Annotated[Optional[Path] , typer.Option(help="Specify the path to the bench directory", show_default=False,rich_help_panel='Host Mode',)] = None,
    fm_restore_db_from_site: Annotated[Optional[str] , typer.Option(help="Specify the site name to import the database from.", show_default=False, rich_help_panel='FM Mode')] = None,
    configure: Annotated[Optional[bool] , typer.Option(help="If not configure then configure and then pull.", show_default=False)] = None,
    restore_db_file_path: Annotated[Optional[Path], typer.Option(help='Restore db file path', callback=validate_db_file_path,show_default=False)] = None,
):
    """
    Pulls the current set of frappe apps and setup new release based on provided config file/flags.

    The config file that you pass will set the default initial configuration.

    Flags are provided to override/add configurations present in config.
    """
    current_locals = locals()

    if host_bench_path:
        current_locals['host'] = {'bench_path': str(host_bench_path.absolute())}

    if fm_restore_db_from_site:
        current_locals['fm'] = {'restore_db_from_site': fm_restore_db_from_site}

    richprint.start('working')
    config: Config = Config.from_toml(config_path, config_content, get_config_overrides(locals=current_locals))

    if len(config.apps) == 0:
        raise RuntimeError("Apps list cannot be empty in [code]pull[/code] command.")

    manager = DeploymentManager(config)

    total_start_time = time.time()

    manager.create_new_release()

    if config.verbose:
        total_end_time = time.time()
        total_elapsed_time = total_end_time - total_start_time
        manager.printer.print(f"Total Time Taken: [bold yellow]{human_readable_time(total_elapsed_time)}[/bold yellow]",emoji_code=":robot_face:")
