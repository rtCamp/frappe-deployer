from pathlib import Path
from typing import Annotated, Optional
from frappe_deployer.config.config import Config
from frappe_deployer.deployment_manager import DeploymentManager
from frappe_manager.logger.log import richprint
import typer
from frappe_deployer.commands import app, configure_basic_deployment_config, validate_cofig_path, get_config_overrides

@app.command()
def cleanup(
    ctx: typer.Context,

    site_name: Annotated[
        Optional[str],
        typer.Argument(help="The name of the site.", show_default=False, metavar="Site Name / Bench Name"),
    ] = None,

    config_path: Annotated[
        Optional[Path], typer.Option("--config-path","-c",help="TOML config path", callback=validate_cofig_path, show_default=False)
    ] = None,
    backup_retain_limit: Annotated[
        int,
        typer.Option(
            "--backup-retain-limit",
            "-b",
            help="Number of backup directories to retain",
            show_default=True
        )
    ] = 0,
    release_retain_limit: Annotated[
        int,
        typer.Option(
            "--release-retain-limit",
            "-r",
            help="Number of release directories to retain (current release is always kept)",
            show_default=True
        )
    ] = 0,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes", "-y",
            help="Auto-approve all cleanup operations without prompting",
            show_default=True
        )
    ] = False,
    show_sizes: Annotated[
        bool,
        typer.Option(
            "--show-sizes", "-s",
            help="Calculate and show directory sizes (may be slow for large directories)",
            show_default=True
        )
    ] = True,
    verbose: Annotated[
        Optional[bool],
        typer.Option("--verbose", "-v", help="Enable verbose output", show_default=False)
    ] = None,
):
    """
    Cleanup deployment backups and releases.
    - Retains specified number of recent backup directories
    - Optionally retains specified number of release directories
    Will sort by timestamp in name before determining which to keep.
    Current release is always preserved.
    """
    current_locals = locals()

    if not config_path:
        current_locals["mode"] = "fm"

    if site_name:
        current_locals.update(configure_basic_deployment_config(site_name))

        richprint.start("working")

        config = Config.from_toml(
            config_file_path=config_path,
            overrides=get_config_overrides(locals=current_locals)
        )

        manager = DeploymentManager(config)
        manager.cleanup_workspace_cache(backup_retain_limit, release_retain_limit, auto_approve=yes, show_sizes=show_sizes)
