from typing import Annotated
from frappe_manager import CLI_BENCHES_DIRECTORY
from frappe_manager.logger.log import richprint
import typer
import subprocess
from typing import Annotated
from frappe_manager import CLI_BENCHES_DIRECTORY
from frappe_manager.logger.log import richprint
import typer
import toml

from frappe_deployer.commands import app

@app.command()
def info(
    ctx: typer.Context,
    site_name: Annotated[
        str,
        typer.Argument(help="The name of the site.", show_default=False, metavar="Site Name / Bench Name"),
    ],
):
    """
    Show release info for a site by inspecting each app's git repository.
    """
    richprint.start("working")

    bench_path = CLI_BENCHES_DIRECTORY / f"{site_name}/workspace/frappe-bench"
    apps_dir = bench_path / "apps"
    if not apps_dir.exists():
        richprint.exit(f"No apps directory found for site {site_name}")

    apps_list = []
    for app_dir in apps_dir.iterdir():
        if not app_dir.is_dir():
            continue
        git_dir = app_dir / ".git"
        if not git_dir.exists():
            continue

        def run_git(cmd):
            try:
                return subprocess.check_output(
                    ["git"] + cmd,
                    cwd=str(app_dir),
                    stderr=subprocess.DEVNULL
                ).decode().strip()
            except Exception:
                return None

        remote = run_git(["remote", "get-url", "origin"])
        branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        commit = run_git(["rev-parse", "HEAD"])
        tag = run_git(["describe", "--tags", "--exact-match"])
        latest_commit_msg = run_git(["log", "-1", "--pretty=%B"])

        if not tag:
            tag = None
        remote_name = run_git(["remote"])
        if remote_name:
            remote_names = remote_name.splitlines()
            if len(remote_names) == 1:
                remote_name = remote_names[0]
            elif remote and remote_names:
                for rn in remote_names:
                    url = run_git(["remote", "get-url", rn])
                    if url == remote:
                        remote_name = rn
                        break
                else:
                    remote_name = remote_names[0]
        else:
            remote_name = None


        app_dict = {
            "repo": remote if remote else app_dir.name,
            "ref": commit if commit else branch if branch else None,
            "app_name": app_dir.name,
            "remote_name": remote_name,
            "tag": tag,
            "latest_commit_msg": latest_commit_msg,
        }
        apps_list.append(app_dict)

    output_dict = {"apps": apps_list}
    print(toml.dumps(output_dict))
