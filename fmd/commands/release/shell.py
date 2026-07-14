import os
import subprocess
from pathlib import Path
from typing import Optional

import typer
from typer_examples import example

from fmd.commands._utils import load_config
from fmd.consts import RELEASE_DIR_NAME


@example(
    "Shell into latest release from config",
    "--config {config_path}",
    detail="Finds the latest release and opens an interactive shell in the build container.",
    config_path="./site.toml",
)
@example(
    "Shell into a specific release",
    "--config {config_path} {release_name}",
    detail="Opens an interactive shell for a specific release directory.",
    config_path="./site.toml",
    release_name="release_20260714_120618",
)
def shell(
    release_name: Optional[str] = typer.Argument(
        None, help="Release name (e.g. release_20260714_120618). Uses latest if omitted."
    ),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to site config TOML file."),
    bench_name: Optional[str] = typer.Option(None, "--bench-name", help="Bench name (when no config file)."),
):
    """Open an interactive shell inside the build container for a release."""
    if not config_path and not bench_name:
        typer.echo("Error: --config/-c or --bench-name is required.")
        raise typer.Exit(1)

    if config_path:
        config = load_config(config_path, skip_repo_validation=True)
        site_name = config.site_name
        if config.ship:
            workspace_root = config_path.resolve().parent
        else:
            workspace_root = config.workspace_root
    else:
        site_name = bench_name
        try:
            from frappe_manager import CLI_BENCHES_DIRECTORY
        except Exception:
            CLI_BENCHES_DIRECTORY = Path("/workspace")
        workspace_root = CLI_BENCHES_DIRECTORY / site_name

    workspace = workspace_root / "workspace"

    if not workspace.exists():
        typer.echo(f"Error: workspace not found at {workspace}")
        raise typer.Exit(1)

    # Determine release directory
    if release_name:
        release_path = workspace / release_name
        if not release_path.exists():
            typer.echo(f"Error: release '{release_name}' not found at {release_path}")
            raise typer.Exit(1)
    else:
        # Find the latest release
        releases = sorted(
            [d for d in workspace.iterdir() if d.is_dir() and d.name.startswith(RELEASE_DIR_NAME)],
            key=lambda d: d.name,
            reverse=True,
        )
        if not releases:
            typer.echo(f"No releases found in {workspace}")
            raise typer.Exit(1)
        release_path = releases[0]
        release_name = release_path.name
        typer.echo(f"Using latest release: {release_name}")

    typer.echo(f"Release path: {release_path}")

    # Pick the image
    if config_path and hasattr(config, "release") and config.release and config.release.runner_image:
        image = config.release.runner_image
    else:
        try:
            import importlib.metadata

            version = importlib.metadata.version("frappe-manager")
            image = f"ghcr.io/rtcamp/frappe-manager-frappe:v{version}"
        except Exception:
            image = "ghcr.io/rtcamp/frappe-manager-frappe:v0.20.0.dev0"

    bench_mount = "/workspace/frappe-bench"
    host_uid = os.getuid()
    host_gid = os.getgid()

    typer.echo(f"Image: {image}")
    typer.echo(f"Mount: {release_path} -> {bench_mount}")
    typer.echo()

    # Build docker run command for interactive shell
    # Must use --entrypoint to bypass the image's default entrypoint (which requires USERID)
    cmd = [
        "docker",
        "run",
        "-it",
        "--rm",
        "--user",
        "root",
        "--entrypoint",
        "/bin/bash",
        "--volume",
        f"{release_path}:{bench_mount}",
        "--workdir",
        bench_mount,
        "--env",
        f"HOME={bench_mount}",
        "--env",
        "USER=frappe",
        "--env",
        f"PATH={bench_mount}/.uv/python-default/bin:{bench_mount}/.fnm/aliases/default/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin",
        "--env",
        f"FNM_DIR={bench_mount}/.fnm",
        "--env",
        f"FNM_MULTISHELL_PATH={bench_mount}/.fnm",
        "--env",
        "FNM_COREPACK_ENABLED=true",
        "--env",
        f"COREPACK_HOME={bench_mount}/.fnm/corepack",
        "--env",
        f"UV_PYTHON_INSTALL_DIR={bench_mount}/.uv/python",
        "--env",
        f"UV_CACHE_DIR={bench_mount}/.uv/cache",
        "--env",
        "UV_PYTHON_DOWNLOADS=automatic",
        "--env",
        "UV_PYTHON_PREFERENCE=only-managed",
        "--env",
        "BENCH_USE_UV=true",
        "--env",
        "PYTHONUNBUFFERED=1",
        image,
        "-c",
        f"usermod -u {host_uid} frappe 2>/dev/null; "
        f"groupmod -g {host_gid} frappe 2>/dev/null; "
        f"chown -R frappe:frappe {bench_mount} 2>/dev/null; "
        f"exec gosu frappe /bin/bash -l",
    ]

    typer.echo(f"Running: {' '.join(cmd)}")
    typer.echo()

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        typer.echo(f"Shell exited with code {e.returncode}")
        raise typer.Exit(code=e.returncode)
    except KeyboardInterrupt:
        typer.echo()
        typer.echo("Exiting shell.")
