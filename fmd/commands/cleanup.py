from pathlib import Path
from typing import Optional

import typer
from typer_examples import example

from fmd.commands._utils import build_runners, get_printer, load_config
from fmd.services.cleanup import CleanupService


@example(
    "Cleanup and auto-approve",
    "--config {config_path} --yes",
    detail="Runs cleanup without prompting for confirmation. Useful in CI or scripts.",
    config_path="./site.toml",
)
@example(
    "Keep last 3 releases",
    "{bench_name} --release-retain-limit 3",
    detail="Deletes all but the 3 most recent releases in the bench workspace.",
    bench_name="mybench",
)
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
    overrides = {"bench_name": bench_name, "site_name": bench_name} if bench_name else None
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
