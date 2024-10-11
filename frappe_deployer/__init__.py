from pathlib import Path
from typing import Annotated
import typer

from frappe_deployer.config.config import Config
from frappe_deployer.consts import LOG_FILE_NAME
from frappe_deployer.deployment_manager import DeploymentManager
from frappe_deployer.exceptions import ConfigPathDoesntExist
from unittest.mock import patch


class CustomLogger:
    def debug(self, msg):
        print(f"Custom debug: {msg}")

patcher = patch('frappe_manager.logger.log.get_logger.__defaults__', (LOG_FILE_NAME.parent, LOG_FILE_NAME.name))
#patcher = patch('frappe_manager.logger.log.get_logger', return_value=CustomLogger())
patcher.start()

cli = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")

def validate_cofig_path(configpath: str):
    if not Path(configpath).exists():
        raise ConfigPathDoesntExist(configpath)
    return Path(configpath)

@cli.command(no_args_is_help=True)
def configure(
    ctx: typer.Context,
    #benchpath: Annotated[str, typer.Argument(help="bench path")],
    config_path: Annotated[str, typer.Option(help='TOML config path',callback=validate_cofig_path)]
):

    config: Config = Config.from_toml(config_path)
    DeploymentManager.configure(config)

@cli.command(no_args_is_help=True)
def pull(
    ctx: typer.Context,
    config_path: Annotated[str, typer.Option(help='TOML config path',callback=validate_cofig_path)]
):

    config: Config = Config.from_toml(config_path)
    manager = DeploymentManager(config)
    manager.create_new_release()



@cli.command(no_args_is_help=True)
def test(
    ctx: typer.Context,
    config_path: Annotated[str, typer.Option(help='TOML config path',callback=validate_cofig_path)]
):

    config: Config = Config.from_toml(config_path)
    manager = DeploymentManager(config)
    manager.bench_symlink_and_restart(manager.current)
