from pathlib import Path
from typing import Annotated, Optional
from frappe_deployer.consts import BYPASS_TOKEN, MAINTENANCE_MODE_CONFIG
from frappe_manager import (
    CLI_BENCHES_DIRECTORY,
    CLI_SERVICES_DIRECTORY,
    CLI_SERVICES_NGINX_PROXY_DIR,
)
from frappe_manager.logger.log import richprint
import typer

from frappe_deployer.commands import app

@app.command(no_args_is_help=True)
def enable_maintenance(
    ctx: typer.Context,
    site_name: Annotated[
        Optional[str],
        typer.Argument(help="The name of the site.", show_default=False, metavar="Site Name / Bench Name"),
    ] = None,
):
    richprint.start("working")

    # check if site exists
    site_config_path: Path = CLI_BENCHES_DIRECTORY / f"{site_name}"

    if not site_config_path.exists():
        richprint.exit(f"Site {site_name} does not exist")

    try:
        # Write maintenance config
        vhostd_config_path: Path = CLI_SERVICES_NGINX_PROXY_DIR / "vhostd" / f"{site_name}_location"
        vhostd_config_path.write_text(MAINTENANCE_MODE_CONFIG.format(BYPASS_TOKEN=BYPASS_TOKEN))

        # Reload nginx to apply changes
        from subprocess import run

        run(
            [
                "docker",
                "compose",
                "-f",
                str(CLI_SERVICES_DIRECTORY / "docker-compose.yml"),
                "restart",
                "global-nginx-proxy",
            ]
        )

        richprint.print(f"Maintenance mode enabled for site {site_name}")
        richprint.print(f"Developer bypass URL: [link]http://{site_name}/{BYPASS_TOKEN}/[/link]")
    except Exception as e:
        richprint.exit(f"Failed to enable maintenance mode: {str(e)}")


@cli.command(no_args_is_help=True)
def disable_maintenance(
    ctx: typer.Context,
    site_name: Annotated[
        Optional[str],
        typer.Argument(help="The name of the site.", show_default=False, metavar="Site Name / Bench Name"),
    ] = None,
):
    richprint.start("working")

    # check if site exists
    site_config_path: Path = CLI_BENCHES_DIRECTORY / f"{site_name}"

    if not site_config_path.exists():
        richprint.exit(f"Site {site_name} does not exist")

    try:
        # Remove maintenance config if it exists
        vhostd_config_path: Path = CLI_SERVICES_NGINX_PROXY_DIR / "vhostd" / f"{site_name}_location"
        if vhostd_config_path.exists():
            vhostd_config_path.unlink()

        # Reload nginx to apply changes
        from subprocess import run

        run(
            [
                "docker",
                "compose",
                "-f",
                str(CLI_SERVICES_DIRECTORY / "docker-compose.yml"),
                "restart",
                "global-nginx-proxy",
            ]
        )

        richprint.print(f"Maintenance mode disabled for site {site_name}")
    except Exception as e:
        richprint.exit(f"Failed to disable maintenance mode: {str(e)}")
