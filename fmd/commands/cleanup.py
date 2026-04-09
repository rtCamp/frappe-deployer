from pathlib import Path
from typing import Optional

import typer

from fmd.commands._utils import build_runners, get_printer, load_config
from fmd.services.cleanup import CleanupService


def cleanup(
    bench_name: Optional[str] = typer.Argument(None, help="Bench name (required when no config file is provided)."),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to site config TOML file."),
    backup_retain_limit: int = typer.Option(0, "--backup-retain-limit", "-b", help="Number of backup dirs to retain."),
    release_retain_limit: int = typer.Option(
        0, "--release-retain-limit", "-r", help="Number of release dirs to retain."
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve all cleanup operations."),
    show_sizes: bool = typer.Option(True, "--show-sizes", help="Calculate and show directory sizes."),
):
    """Cleanup deployment backups and releases."""
    overrides = {"site_name": bench_name} if bench_name else None
    config = load_config(config_path, overrides=overrides)
    printer = get_printer()
    image_runner, exec_runner, host_runner = build_runners(config)
    printer.start("Working")
    service = CleanupService(exec_runner, host_runner, config, printer)
    service.cleanup_workspace_cache(
        config.workspace_root,
        config.bench_path,
        backup_retain_limit,
        release_retain_limit,
        auto_approve=yes,
        show_sizes=show_sizes,
    )
    printer.stop()
