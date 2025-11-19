from enum import Enum
from git import Optional
import typer
from pathlib import Path
from typing_extensions import Annotated
import os

from frappe_deployer.config.config import Config
from frappe_deployer.build_manager import BuildManager
from frappe_deployer.commands import app, get_config_overrides, validate_cofig_path
from frappe_manager.logger.log import richprint

class ImageType(str, Enum):
    frappe = "frappe"
    nginx = "nginx"
    all = "all"

@app.command(name="build-image", no_args_is_help=True)
def build_image(
    ctx: typer.Context,
    site_name: Annotated[
        Optional[str],
        typer.Argument(help="The name of the site.", show_default=False, metavar="Site Name / Bench Name"),
    ] = None,
    config_path: Annotated[
        Optional[Path], typer.Option(help="TOML config path", callback=validate_cofig_path, show_default=False)
    ] = None,
    config_content: Annotated[
        Optional[str], typer.Option(help="TOML config string content", show_default=False)
    ] = None,
    github_token: Annotated[
        Optional[str], typer.Option(help="The GitHub personal access token", show_default=False)
    ] = None,
    output_dir: Annotated[Path, typer.Option(help="Output directory for baked bench and Dockerfiles.", rich_help_panel="General")] = Path.cwd() / "outputs",
    force: Annotated[bool, typer.Option(help="Force build image.", rich_help_panel="General")] = False,
    push: Annotated[bool, typer.Option(help="Toggle to allow pushing the docker image", rich_help_panel="General")] = False,
    image_type: Annotated[ImageType, typer.Option(help="Specify which image to build.", case_sensitive=False, rich_help_panel="General")] = ImageType.all,
):
    """
    Builds the docker images for the project.
    """

    current_locals = locals()
    richprint.start("working")

    bench_path = output_dir / "bench"

    current_locals["build_frappe"] = {"bench_path": str(bench_path.absolute()), "push": push}
    current_locals["build_nginx"] = {"name": "frappe-nginx", "push": push}

    config: Config = Config.from_toml(config_path, config_content, get_config_overrides(locals=current_locals))

    if len(config.apps) == 0:
        raise RuntimeError("Apps list cannot be empty in [code]pull[/code] command.")

    builder = BuildManager(config)
    builder.build_images(force=force, image_type=image_type.value)
