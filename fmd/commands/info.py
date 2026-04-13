import subprocess
from pathlib import Path
from typing import Optional

import toml
import typer
from typer_examples import example

from fmd.commands._utils import load_config


@example(
    "Info from config file",
    "--config {config_path}",
    detail="Reads bench path from config and shows git info for all apps.",
    config_path="./site.toml",
)
@example(
    "Info by bench name",
    "{bench_name}",
    detail="Inspects each app's git repository in the bench and prints commit, branch, and tag info.",
    bench_name="mybench",
)
def info(
    bench_name: Optional[str] = typer.Argument(None, help="Bench name (required when no config file is provided)."),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to site config TOML file."),
):
    """Show release info by inspecting each app's git repository."""
    overrides = {"bench_name": bench_name, "site_name": bench_name} if bench_name else None
    config = load_config(config_path, overrides=overrides)
    apps_dir = config.bench_path / "apps"
    if not apps_dir.exists():
        typer.echo(f"No apps directory found at {apps_dir}", err=True)
        raise typer.Exit(1)

    apps_list = []
    for app_dir in sorted(apps_dir.iterdir()):
        if not app_dir.is_dir() or not (app_dir / ".git").exists():
            continue

        def _git(cmd, _cwd=app_dir):
            try:
                return subprocess.check_output(["git"] + cmd, cwd=str(_cwd), stderr=subprocess.DEVNULL).decode().strip()
            except Exception:
                return None

        remote = _git(["remote", "get-url", "origin"])
        branch = _git(["rev-parse", "--abbrev-ref", "HEAD"])
        commit = _git(["rev-parse", "HEAD"])
        tag = _git(["describe", "--tags", "--exact-match"]) or None

        remote_name = _git(["remote"])
        if remote_name:
            names = remote_name.splitlines()
            if len(names) == 1:
                remote_name = names[0]
            elif remote:
                for n in names:
                    if _git(["remote", "get-url", n]) == remote:
                        remote_name = n
                        break
                else:
                    remote_name = names[0]
        else:
            remote_name = None

        apps_list.append(
            {
                "app_name": app_dir.name,
                "repo": remote if remote else app_dir.name,
                "ref": commit if commit else branch,
                "remote_name": remote_name,
                "tag": tag,
                "latest_commit_msg": _git(["log", "-1", "--pretty=%B"]),
            }
        )

    typer.echo(toml.dumps({"apps": apps_list}))
