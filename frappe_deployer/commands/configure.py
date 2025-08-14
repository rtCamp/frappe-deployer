from pathlib import Path
from typing import Annotated, Optional
from frappe_manager.logger.log import richprint
import typer
from frappe_deployer.config.config import Config
from frappe_deployer.deployment_manager import DeploymentManager

from frappe_deployer.commands import ModeEnum, app, configure_basic_deployment_config, get_config_overrides, validate_cofig_path
@app.command(no_args_is_help=True)
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


