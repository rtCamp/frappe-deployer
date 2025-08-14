from pathlib import Path
import time
from typing import Annotated, List, Optional
from frappe_manager.logger.log import richprint
import typer
from frappe_deployer import validate_cofig_path
from frappe_deployer.config.config import Config
from frappe_deployer.deployment_manager import DeploymentManager
from frappe_deployer.helpers import human_readable_time

from frappe_deployer.commands import app, get_config_overrides, validate_db_file_path


@app.command(no_args_is_help=True)
def pull(
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
    mode: Annotated[
        Optional[str],
        typer.Option("--mode", "-m", help="Mode of operation, either 'host' or 'fm'.", show_default=False),
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
    releases_retain_limit: Annotated[
        Optional[int], typer.Option("--releases-retain-limit", help="Number of releases to retain", show_default=False)
    ] = None,
    remove_remote: Annotated[
        Optional[bool], typer.Option(help="Remove remote after cloning", show_default=False)
    ] = None,
    rollback: Annotated[Optional[bool], typer.Option(help="Enable/Disable rollback", show_default=False)] = None,
    maintenance_mode: Annotated[
        Optional[bool], typer.Option(help="Enable/Disable maintenance mode", show_default=False)
    ] = None,
    maintenance_mode_phases: Annotated[
        Optional[List[str]], typer.Option(help="For which phases maintenance mode will be enabled.", show_default=False)
    ] = None,
    search_replace: Annotated[
        Optional[bool], typer.Option(help="Enable search and replace in database.", show_default=False)
    ] = None,
    run_bench_migrate: Annotated[
        Optional[bool], typer.Option(help="Enable/Disable 'bench migrate' run", show_default=False)
    ] = None,
    migrate_timeout: Annotated[Optional[int], typer.Option(help="Migrate timeout", show_default=False)] = None,
    wait_workers: Annotated[
        Optional[bool],
        typer.Option(help="Whether to enable waiting for workers", show_default=False, rich_help_panel="FM Mode"),
    ] = None,
    wait_workers_timeout: Annotated[
        Optional[int], typer.Option(help="Wait workers timeout", show_default=False, rich_help_panel="FM Mode")
    ] = None,
    backups: Annotated[Optional[bool], typer.Option(help="Enable/Disable taking backups")] = None,
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
    host_bench_path: Annotated[
        Optional[Path],
        typer.Option(
            help="Specify the path to the bench directory",
            show_default=False,
            rich_help_panel="Host Mode",
        ),
    ] = None,
    fm_restore_db_from_site: Annotated[
        Optional[str],
        typer.Option(
            help="Specify the site name to import the database from.", show_default=False, rich_help_panel="FM Mode"
        ),
    ] = None,
    configure: Annotated[
        Optional[bool], typer.Option(help="If not configure then configure and then pull.", show_default=False)
    ] = None,
    restore_db_file_path: Annotated[
        Optional[Path], typer.Option(help="Restore db file path", callback=validate_db_file_path, show_default=False)
    ] = None,
    remote_name: Annotated[
        Optional[str],
        typer.Option(
            "--remote-name", help="Name of the remote to use during cloning (default: upstream)", show_default=False
        ),
    ] = None,
    fc_key: Annotated[
        Optional[str],
        typer.Option("--fc-key", help="Frappe Cloud API key", show_default=False, rich_help_panel="Frappe Cloud"),
    ] = None,
    fc_secret: Annotated[
        Optional[str],
        typer.Option("--fc-secret", help="Frappe Cloud API secret", show_default=False, rich_help_panel="Frappe Cloud"),
    ] = None,
    fc_site_name: Annotated[
        Optional[str],
        typer.Option(
            "--fc-site-name", help="Frappe Cloud Site Name", show_default=False, rich_help_panel="Frappe Cloud"
        ),
    ] = None,
    fc_team_name: Annotated[
        Optional[str],
        typer.Option(
            "--fc-team-name", help="Frappe Cloud Team Name", show_default=False, rich_help_panel="Frappe Cloud"
        ),
    ] = None,
    fc_use_deps: Annotated[
        Optional[bool],
        typer.Option(
            "--fc-use-deps",
            help="Use Frappe Cloud dependencies list i.e python version, node version",
            show_default=False,
            rich_help_panel="Frappe Cloud",
        ),
    ] = None,
    fc_use_db: Annotated[
        Optional[str],
        typer.Option("--fc-use-db", help="Frappe Cloud Site Name", show_default=False, rich_help_panel="Frappe Cloud"),
    ] = None,
):
    """
    Pulls the current set of frappe apps and setup new release based on provided config file/flags.

    The config file that you pass will set the default initial configuration.

    Flags are provided to override/add configurations present in config.
    """
    current_locals = locals()

    if host_bench_path:
        current_locals["host"] = {"bench_path": str(host_bench_path.absolute())}

    if fm_restore_db_from_site:
        current_locals["fm"] = {"restore_db_from_site": fm_restore_db_from_site}

    richprint.start("working")
    config: Config = Config.from_toml(config_path, config_content, get_config_overrides(locals=current_locals))

    if len(config.apps) == 0:
        raise RuntimeError("Apps list cannot be empty in [code]pull[/code] command.")

    manager = DeploymentManager(config)
    manager.configure_basic_info()

    total_start_time = time.time()

    manager.create_new_release()

    if config.verbose:
        total_end_time = time.time()
        total_elapsed_time = total_end_time - total_start_time
        manager.printer.print(
            f"Total Time Taken: [bold yellow]{human_readable_time(total_elapsed_time)}[/bold yellow]",
            emoji_code=":robot_face:",
        )
