from pathlib import Path
from typing import Annotated
from frappe_deployer.deployment_manager import DeploymentManager
from frappe_manager import CLI_BENCHES_DIRECTORY
from frappe_manager.logger.log import richprint
from frappe_deployer.config.config import Config
import typer

from frappe_deployer.commands import app

@app.command(no_args_is_help=True)
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

    site_config_path: Path = CLI_BENCHES_DIRECTORY / f"{site_name}"

    if not site_config_path.exists():
        richprint.exit(f"Site {site_name} does not exist")

    try:
        config = Config(site_name=site_name, bench_path=site_config_path / "workspace/frappe-bench", apps=[], mode="fm")
        manager = DeploymentManager(config)
        manager.configure_basic_info()

        manager.search_and_replace_in_database(
            search=search, replace=replace, dry_run=dry_run, verbose=manager.config.verbose
        )
    except Exception as e:
        richprint.warning(f"Failed to perform search and replace: {str(e)}")
