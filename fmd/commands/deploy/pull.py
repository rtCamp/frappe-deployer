from pathlib import Path
from typing import List, Optional
import subprocess
import tempfile
from datetime import datetime

import typer
from typer_examples import example

from fmd.commands._utils import build_runners, get_printer, load_config, parse_app_option
from fmd.managers.pull import PullManager
from fmd.config.config import Config


def _deploy_remote(config: Config, printer) -> None:
    """Execute pull deployment on remote server via SSH."""
    pull_config = config.pull
    if pull_config is None:
        raise ValueError("Remote deployment requires [pull] section in config")
    
    ssh_server = pull_config.ssh_server
    ssh_user = pull_config.ssh_user
    ssh_port = pull_config.ssh_port
    
    # Determine FMD source - prefer config, fallback to env var, then PyPI
    fmd_source = pull_config.fmd_source
    if not fmd_source:
        import os
        fmd_source = os.environ.get("FMD_ACTION_PATH")
    if not fmd_source:
        fmd_source = "fmd"
    
    current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    # Determine FMD source to install on remote
    if "/" in fmd_source and ("github.com" in fmd_source or fmd_source.startswith("git@")):
        install_source = fmd_source
    elif Path(fmd_source).exists():
        remote_fmd_src = f"/tmp/fmd_src_{current_datetime}"
        printer.print(f"Syncing local FMD source to remote: {remote_fmd_src}")
        subprocess.run(
            [
                "rsync", "-az", "--exclude=.git", "--exclude=__pycache__", "--exclude=*.pyc",
                "-e", f"ssh -p {ssh_port} -o StrictHostKeyChecking=no",
                f"{fmd_source}/", f"{ssh_user}@{ssh_server}:{remote_fmd_src}/"
            ],
            check=True
        )
        install_source = remote_fmd_src
    else:
        install_source = fmd_source
    
    # Setup uv if not present
    printer.print("Setting up uv on remote server")
    subprocess.run(
        ["ssh", "-p", str(ssh_port), "-o", "StrictHostKeyChecking=no", f"{ssh_user}@{ssh_server}",
         f"cd /home/{ssh_user} && test -x /home/{ssh_user}/.local/bin/uv || curl -LsSf https://astral.sh/uv/install.sh | sh"],
        check=True
    )
    
    printer.print("Installing fmd in remote venv")
    subprocess.run(
        ["ssh", "-p", str(ssh_port), "-o", "StrictHostKeyChecking=no", f"{ssh_user}@{ssh_server}",
         f"cd /home/{ssh_user} && mkdir -p /home/{ssh_user}/.fmd/logs && rm -rf /home/{ssh_user}/.fmd/venv && "
         f"/home/{ssh_user}/.local/bin/uv venv /home/{ssh_user}/.fmd/venv --python 3.13 && "
         f"/home/{ssh_user}/.local/bin/uv pip install --python /home/{ssh_user}/.fmd/venv/bin/python {install_source}"],
        check=True
    )
    
    printer.print("[DEBUG] Checking if frappe_manager is installed on remote")
    result = subprocess.run(
        ["ssh", "-p", str(ssh_port), "-o", "StrictHostKeyChecking=no", f"{ssh_user}@{ssh_server}",
         f"/home/{ssh_user}/.fmd/venv/bin/python -c 'try: import frappe_manager; print(f\"frappe_manager found: {{frappe_manager.CLI_BENCHES_DIRECTORY}}\"); except: print(\"frappe_manager not installed\")'"],
        capture_output=True,
        text=True
    )
    printer.print(f"[DEBUG] frappe_manager check result: {result.stdout.strip()}")
    
    printer.print(f"[DEBUG] Checking USER environment variable on remote")
    result = subprocess.run(
        ["ssh", "-p", str(ssh_port), "-o", "StrictHostKeyChecking=no", f"{ssh_user}@{ssh_server}",
         "echo $USER"],
        capture_output=True,
        text=True
    )
    printer.print(f"[DEBUG] Remote USER={result.stdout.strip()}")
    
    # Write config to temp file and rsync to remote
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        local_config_path = Path(f.name)
    
    remote_config = config.model_copy(deep=True)
    remote_config.pull = None
    if not remote_config.release:
        from fmd.config.release import ReleaseConfig
        remote_config.release = ReleaseConfig()
    remote_config.release.mode = "host"
    
    printer.print(f"[DEBUG] Remote config before TOML write: release.mode={remote_config.release.mode}")
    remote_config.to_toml(local_config_path)
    
    with open(local_config_path, 'r') as f:
        toml_content = f.read()
        printer.print(f"[DEBUG] TOML content written to {local_config_path}:")
        printer.print(toml_content)
    
    remote_config_path = f"/tmp/fmd_config_{current_datetime}.toml"
    printer.print(f"Syncing config to remote: {remote_config_path}")
    subprocess.run(
        ["rsync", "-az", "-e", f"ssh -p {ssh_port} -o StrictHostKeyChecking=no",
         str(local_config_path), f"{ssh_user}@{ssh_server}:{remote_config_path}"],
        check=True
    )
    local_config_path.unlink()
    
    # Build command
    cmd_parts = [
        f"/home/{ssh_user}/.fmd/venv/bin/fmd", "deploy", "pull",
        config.site_name, "--config", remote_config_path
    ]
    if config.github_token:
        cmd_parts.extend(["--github-token", config.github_token])
    
    remote_cmd = " ".join(cmd_parts)
    
    # Execute pull command on remote
    printer.print("Executing pull deployment on remote server")
    result = subprocess.run(
        ["ssh", "-p", str(ssh_port), "-o", "StrictHostKeyChecking=no", f"{ssh_user}@{ssh_server}",
         f"cd /home/{ssh_user}/.fmd/logs && {remote_cmd} 2>&1"],
        check=False
    )
    
    # Cleanup remote FMD source if we uploaded it
    if "/" in fmd_source and Path(fmd_source).exists():
        subprocess.run(
            ["ssh", "-p", str(ssh_port), "-o", "StrictHostKeyChecking=no", f"{ssh_user}@{ssh_server}",
             f"rm -rf {install_source}"],
            check=False
        )
    
    if result.returncode != 0:
        raise typer.Exit(code=result.returncode)


@example(
    "Deploy with Frappe Cloud integration",
    "{bench_name} --fc-key {fc_key} --fc-secret {fc_secret} --fc-site {fc_site}",
    detail="Pulls FC app list and DB backup, then deploys. Requires FC API credentials.",
    bench_name="mybench",
    fc_key="your-key",
    fc_secret="your-secret",
    fc_site="mysite.frappe.cloud",
)
@example(
    "Deploy with explicit apps",
    "{bench_name} --app frappe/frappe:version-15 --app frappe/erpnext:version-15",
    detail="Overrides config apps list with specified repos and refs.",
    bench_name="mybench",
)
@example(
    "Deploy from config file",
    "--config {config_path}",
    detail="Reads bench name and app list from the TOML config file. Full deploy: configure → create → switch.",
    config_path="./site.toml",
)
def pull(
    bench_name: Optional[str] = typer.Argument(None, help="Bench name (required when no config file is provided)."),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to site config TOML file."),
    apps: List[str] = typer.Option(
        [], "--app", "-a", help="App in format org/repo:ref[:subdir_path]. Repeatable.", show_default=False
    ),
    github_token: Optional[str] = typer.Option(
        None, "--github-token", help="GitHub personal access token.", show_default=False
    ),
    python_version: Optional[str] = typer.Option(
        None,
        "--python-version",
        "-p",
        help="Python version for venv.",
        show_default=False,
        rich_help_panel="Release Options",
    ),
    node_version: Optional[str] = typer.Option(
        None,
        "--node-version",
        "-n",
        help="Node.js version to install via fnm.",
        show_default=False,
        rich_help_panel="Release Options",
    ),
    releases_retain_limit: Optional[int] = typer.Option(
        None,
        "--releases-retain-limit",
        help="Number of releases to retain.",
        show_default=False,
        rich_help_panel="Release Options",
    ),
    symlink_subdir_apps: Optional[bool] = typer.Option(
        None,
        "--symlink-subdir-apps/--no-symlink-subdir-apps",
        help="Symlink all subdir apps.",
        rich_help_panel="Release Options",
    ),
    migrate: Optional[bool] = typer.Option(
        None, "--migrate/--no-migrate", help="Run bench migrate on switch.", rich_help_panel="Switch Options"
    ),
    migrate_timeout: Optional[int] = typer.Option(
        None,
        "--migrate-timeout",
        help="Migrate timeout in seconds.",
        show_default=False,
        rich_help_panel="Switch Options",
    ),
    maintenance_mode: Optional[bool] = typer.Option(
        None,
        "--maintenance-mode/--no-maintenance-mode",
        help="Enable maintenance mode during switch.",
        rich_help_panel="Switch Options",
    ),
    backups: Optional[bool] = typer.Option(
        None, "--backups/--no-backups", help="Take DB backup before switch.", rich_help_panel="Switch Options"
    ),
    rollback: Optional[bool] = typer.Option(
        None,
        "--rollback/--no-rollback",
        help="Roll back to previous release on failure.",
        rich_help_panel="Switch Options",
    ),
    search_replace: Optional[bool] = typer.Option(
        None,
        "--search-replace/--no-search-replace",
        help="Run search-and-replace in DB after restore.",
        rich_help_panel="Switch Options",
    ),
    drain_workers: Optional[bool] = typer.Option(
        None,
        "--drain-workers/--no-drain-workers",
        help="Drain workers before restart.",
        rich_help_panel="Switch Options",
    ),
    sync_workers: Optional[bool] = typer.Option(
        None,
        "--sync-workers/--no-sync-workers",
        help="Sync to remote workers after deploy.",
        rich_help_panel="Switch Options",
    ),
    fc_key: Optional[str] = typer.Option(
        None, "--fc-key", help="Frappe Cloud API key.", show_default=False, rich_help_panel="Frappe Cloud"
    ),
    fc_secret: Optional[str] = typer.Option(
        None, "--fc-secret", help="Frappe Cloud API secret.", show_default=False, rich_help_panel="Frappe Cloud"
    ),
    fc_site: Optional[str] = typer.Option(
        None, "--fc-site", help="Frappe Cloud site name.", show_default=False, rich_help_panel="Frappe Cloud"
    ),
    fc_team: Optional[str] = typer.Option(
        None, "--fc-team", help="Frappe Cloud team name.", show_default=False, rich_help_panel="Frappe Cloud"
    ),
    fc_use_deps: Optional[bool] = typer.Option(
        None,
        "--fc-use-deps/--no-fc-use-deps",
        help="Use FC dependencies (python version etc).",
        rich_help_panel="Frappe Cloud",
    ),
    fc_use_db: Optional[bool] = typer.Option(
        None,
        "--fc-use-db/--no-fc-use-db",
        help="Restore from latest FC DB backup on switch.",
        rich_help_panel="Frappe Cloud",
    ),
    fc_use_apps: Optional[bool] = typer.Option(
        None,
        "--fc-use-apps/--no-fc-use-apps",
        help="Merge FC app list into config apps.",
        rich_help_panel="Frappe Cloud",
    ),
    rw_server: Optional[str] = typer.Option(
        None,
        "--rw-server",
        "--remote-worker-server-ip",
        help="Remote worker server IP/domain.",
        show_default=False,
        rich_help_panel="Remote Worker",
    ),
    rw_user: Optional[str] = typer.Option(
        None,
        "--rw-user",
        "--remote-worker-ssh-user",
        help="Remote worker SSH user.",
        show_default=False,
        rich_help_panel="Remote Worker",
    ),
    rw_port: Optional[int] = typer.Option(
        None,
        "--rw-port",
        "--remote-worker-ssh-port",
        help="Remote worker SSH port.",
        show_default=False,
        rich_help_panel="Remote Worker",
    ),
):
    """Full deploy: configure (if needed) → create release → switch."""
    overrides: dict = {}
    if bench_name is not None:
        overrides["bench_name"] = bench_name
        if "site_name" not in overrides:
            overrides["site_name"] = bench_name
    if apps:
        overrides["apps"] = parse_app_option(apps)
    if github_token is not None:
        overrides["github_token"] = github_token

    switch: dict = {}
    if migrate is not None:
        switch["migrate"] = migrate
    if migrate_timeout is not None:
        switch["migrate_timeout"] = migrate_timeout
    if maintenance_mode is not None:
        switch["maintenance_mode"] = maintenance_mode
    if backups is not None:
        switch["backups"] = backups
    if rollback is not None:
        switch["rollback"] = rollback
    if search_replace is not None:
        switch["search_replace"] = search_replace
    if drain_workers is not None:
        switch["drain_workers"] = drain_workers
    if sync_workers is not None:
        switch["sync_workers"] = sync_workers
    if switch:
        overrides["switch"] = switch

    release: dict = {}
    if releases_retain_limit is not None:
        release["releases_retain_limit"] = releases_retain_limit
    if symlink_subdir_apps is not None:
        release["symlink_subdir_apps"] = symlink_subdir_apps
    if python_version is not None:
        release["python_version"] = python_version
    if node_version is not None:
        release["node_version"] = node_version
    if fc_use_deps is not None:
        release["use_fc_deps"] = fc_use_deps
    if fc_use_apps is not None:
        release["use_fc_apps"] = fc_use_apps
    if release:
        overrides["release"] = release

    if fc_key or fc_secret or fc_site or fc_team:
        fc: dict = {}
        if fc_key:
            fc["api_key"] = fc_key
        if fc_secret:
            fc["api_secret"] = fc_secret
        if fc_site:
            fc["site_name"] = fc_site
        if fc_team:
            fc["team_name"] = fc_team
        overrides["fc"] = fc

    if fc_use_db is not None:
        if "switch" not in overrides:
            overrides["switch"] = {}
        overrides["switch"]["use_fc_db"] = fc_use_db

    if rw_server:
        rw: dict = {"server_ip": rw_server}
        if rw_user:
            rw["ssh_user"] = rw_user
        if rw_port:
            rw["ssh_port"] = rw_port
        overrides["remote_worker"] = rw

    config = load_config(config_path, overrides=overrides or None, create_if_missing=True)
    printer = get_printer()
    
    # Check if [pull] section exists - if yes, execute remotely
    if config.pull is not None:
        printer.start("Deploying remotely")
        _deploy_remote(config, printer)
        printer.stop()
        typer.echo("Remote deploy complete.")
    else:
        # Local execution - existing behavior
        image_runner, exec_runner, host_runner = build_runners(config)
        printer.start("Deploying")
        manager = PullManager(config, exec_runner, exec_runner, host_runner, printer)
        manager.deploy()
        printer.stop()
        typer.echo("Deploy complete.")
