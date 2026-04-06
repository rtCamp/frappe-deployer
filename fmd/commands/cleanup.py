from pathlib import Path

import typer

from fmd.commands._utils import build_runners, get_printer, load_config
from fmd.services.cleanup import CleanupService


def cleanup(
    config_path: Path = typer.Argument(..., help="Path to site config TOML file."),
    backup_retain_limit: int = typer.Option(0, "--backup-retain-limit", "-b", help="Number of backup dirs to retain."),
    release_retain_limit: int = typer.Option(
        0, "--release-retain-limit", "-r", help="Number of release dirs to retain."
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve all cleanup operations."),
    show_sizes: bool = typer.Option(True, "--show-sizes", "-s", help="Calculate and show directory sizes."),
):
    """Cleanup deployment backups and releases."""
    config = load_config(config_path)
    printer = get_printer()
    image_runner, exec_runner, host_runner = build_runners(config)
    printer.start("Working")
    service = CleanupService(exec_runner, host_runner, config, printer)
    service.cleanup_workspace_cache(
        config.deploy_dir_path,
        config.bench_path,
        backup_retain_limit,
        release_retain_limit,
        auto_approve=yes,
        show_sizes=show_sizes,
    )
    printer.stop()
