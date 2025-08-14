from pathlib import Path
from typing import Annotated

from frappe_deployer.deployment_manager import DeploymentManager
from frappe_manager import CLI_BENCHES_DIRECTORY
from frappe_manager.logger.log import richprint
import typer

from frappe_deployer.commands import app, parse_apps

@app.command(no_args_is_help=True)
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
