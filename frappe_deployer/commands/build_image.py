from git import Optional
import typer
from pathlib import Path
from typing_extensions import Annotated
import os

from frappe_deployer.config.config import Config
from frappe_deployer.build_manager import BuildManager
from frappe_deployer.commands import app, get_config_overrides, validate_cofig_path # Added validate_cofig_path
from frappe_manager.logger.log import richprint

@app.command(name="build-image", no_args_is_help=True)
def build_image(
    ctx: typer.Context,
    config_path: Annotated[
        Optional[Path], typer.Option(help="TOML config path", callback=validate_cofig_path, show_default=False)
    ] = None,
    config_content: Annotated[
        Optional[str], typer.Option(help="TOML config string content", show_default=False)
    ] = None,
    output_dir: Annotated[Path, typer.Option(help="Output directory for baked bench and Dockerfiles.", rich_help_panel="General")] = Path.cwd() / "outputs",
    force: Annotated[bool, typer.Option(help="Force build image.", rich_help_panel="General")] = False,
):
    """
    Builds the docker images for the project.
    """

    current_locals = locals()
    richprint.start("working")

    bench_path = output_dir / "bench"

    current_locals["build_frappe"] = {"bench_path": str(bench_path.absolute())}

    config: Config = Config.from_toml(config_path, config_content, get_config_overrides(locals=current_locals))

    if len(config.apps) == 0:
        raise RuntimeError("Apps list cannot be empty in [code]pull[/code] command.")

    # Instantiate BuildManager and build images
    builder = BuildManager(config, output_dir=output_dir)
    builder.build_images(force=force)
