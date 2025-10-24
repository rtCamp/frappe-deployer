from pathlib import Path
import time
from typing import Annotated, Optional
from frappe_manager.logger.log import richprint
import typer
from frappe_deployer.build_manager import BuildManager
from frappe_deployer.config.config import Config
from frappe_deployer.helpers import human_readable_time

from frappe_deployer.commands import app, get_config_overrides, parse_apps, validate_cofig_path

@app.command(no_args_is_help=True)
def build(
    ctx: typer.Context,
    bench_path: Annotated[
        Path, typer.Argument(help="Path of the file in which the bench environment will be built.", show_default=False)
    ],
    config_path: Annotated[
        Optional[Path], typer.Option(help="TOML config path", callback=validate_cofig_path, show_default=False)
    ] = None,
    config_content: Annotated[
        Optional[str], typer.Option(help="TOML config string content", show_default=False)
    ] = None,
    apps: Annotated[
        list[str],
        typer.Option(
            "--apps",
            "-a",
            help="List of apps in the format [underline]org_name/repo_name:branch[/underline]",
            callback=parse_apps,
            show_default=False,
        ),
    ] = [],
    github_token: Annotated[
        Optional[str], typer.Option(help="The GitHub personal access token", show_default=False)
    ] = None,
    python_version: Annotated[
        Optional[str],
        typer.Option(
            "--python-version",
            "-p",
            help="Specifiy the python version used to create bench python env. Defaults to whatever currently installed python version on your system.",
            show_default=False,
        ),
    ] = None,
    uv: Annotated[
        Optional[bool],
        typer.Option(
            "--uv",
            help="Use [underline]uv[/underline] instead of [underline]pip[/underline] to manage and install packages",
            show_default=False,
        ),
    ] = None,
    verbose: Annotated[
        Optional[bool], typer.Option("--verbose", "-v", help="Enable verbose output", show_default=False)
    ] = None,
    remove_remote: Annotated[
        Optional[bool], typer.Option(help="Remove remote after cloning", show_default=False)
    ] = None,
):
    """
    Pulls the current set of frappe apps and setup new frappe-bench based on provided config file/flags.

    The config file that you pass will set the default initial configuration.

    Flags are provided to override/add configurations present in config.
    """
    current_locals = locals()
    richprint.start("working")

    if bench_path:
        current_locals["build"] = {"bench_path": str(bench_path.absolute())}

    if not bench_path.exists():
        bench_path.mkdir()

    config: Config = Config.from_toml(config_path, config_content, get_config_overrides(locals=current_locals))

    if len(config.apps) == 0:
        raise RuntimeError("Apps list cannot be empty in [code]pull[/code] command.")

    manager = BuildManager(config)
    total_start_time = time.time()
    manager.bake()

    if config.verbose:
        total_end_time = time.time()
        total_elapsed_time = total_end_time - total_start_time
        manager.printer.print(
            f"Total Time Taken: [bold yellow]{human_readable_time(total_elapsed_time)}[/bold yellow]",
            emoji_code=":robot_face:",
        )
