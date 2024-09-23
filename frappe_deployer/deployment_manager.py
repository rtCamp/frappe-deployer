import shutil
import git
from pathlib import Path
from typing import Literal, Optional, Self

from git.exc import GitCommandError

from frappe_manager.display_manager import DisplayManager

from frappe_deployer.helpers import gen_name_with_timestamp, get_relative_path
from frappe_deployer.release_directory import BenchDirectory

RELEASE_DIR_NAME = 'release'
BENCH_DIR_NAME = 'frappe-bench'
DATA_DIR_NAME = 'deployment-data'

class DeploymentManager:
    apps: list[dict[str, str]]
    path: Path
    mode: Literal['fm','host'] = 'host'

    def __init__(self, path:Path, apps: list[dict[str,str]], mode: Literal['fm','host'] = 'host', current_bench_name: str = BENCH_DIR_NAME ) -> None:
        self.apps = apps
        self.mode = mode
        self.path = path
        self.printer = DisplayManager.DisplayManager()

        self.current = BenchDirectory(self.path / current_bench_name)
        self.data = BenchDirectory(self.path / DATA_DIR_NAME)
        self.new = BenchDirectory(self.path / gen_name_with_timestamp(RELEASE_DIR_NAME))
        self.printer.start('Working')

    @staticmethod
    def configure(bench_path: Path, mode: Literal['fm','host'] = 'host' ):
        release =  DeploymentManager(bench_path.parent, [], mode,bench_path.name)

        if not release.data.path.exists:
            release.printer.change_head('Creating release data dir')
            release.data.path.mkdir()
            release.printer.print('Created release data dir')

        # move all sites
        release.printer.change_head('Moving sites into data dir')
        for site in release.current.list_sites():
            data_site_path = release.data.sites / site.name
            shutil.move(str(site.absolute()), str(data_site_path.absolute()))
            data_site_path.symlink_to(get_relative_path(site,data_site_path), True)
            release.printer.print(f'Moved {site.name} and created symlink')

        # nginx.conf
        if release.current.nginx_conf.exists():
            release.printer.change_head('Moving nginx.conf into data dir')
            shutil.move(str(release.current.nginx_conf.absolute()),(release.data.nginx_conf.absolute()))
            release.current.nginx_conf.symlink_to(get_relative_path(release.current.nginx_conf,release.data.nginx_conf), True)
            release.printer.print('Moved nginx.conf and created symlink')

        # common_site_config.json
        if release.current.common_site_config.exists():
            release.printer.change_head('Moving common_site_config.json into data dir')
            shutil.move(str(release.current.common_site_config.absolute()),(release.data.common_site_config.absolute()))
            release.current.common_site_config.symlink_to(get_relative_path(release.current.common_site_config,release.data.common_site_config), True)
            release.printer.print('Moved common_site_config.json and created symlink')

        # logs
        if release.current.logs.exists():
            release.printer.change_head('Moving logs into data dir')
            shutil.move(str(release.current.logs.absolute()),str(release.data.logs.absolute()))
            release.current.logs.symlink_to(get_relative_path(release.current.logs,release.data.logs), True)
            release.printer.print('Moved logs and created symlink')

        # bench
        release.printer.change_head(f'Moving bench directory, creating initial release')
        shutil.move(str(release.current.path.absolute()), str(release.new.path.absolute()))
        release.new.path.symlink_to(get_relative_path(release.current.path,release.new.path), True)
        release.printer.print('Moved bench directory and created symlink')
        release.printer.stop()

    def create_new_release(self):
        self.new.path.mkdir(exist_ok=True)
        self.new.apps.mkdir(exist_ok=True)
        self.clone_app('frappe/frappe', 'v13.0.0', self.new.apps / 'frappe', token='your_github_token')


    def clone_app(self, repo: str, ref: str, clone_path: Path, token: Optional[str] = None):
        """
        Clone a specific ref (tag/branch/commit) from a GitHub repository.

        :param repo: The repository in the format <owner>/<repo>, e.g., frappe/frappe.
        :param ref: The ref to checkout, can be a tag, branch, or commit.
        :param clone_path: The path where the repository should be cloned.
        :param token: Optional GitHub user token for HTTPS authentication.
        """

        # Attempt to clone using HTTPS
        try:
            if token:
                repo_url = f"https://{token}:x-oauth-basic@github.com/{repo}.git"
            else:
                repo_url = f"https://github.com/{repo}.git"

            cloned_repo = git.Repo.clone_from(repo_url, clone_path)
        except GitCommandError:

            # If HTTPS fails, fall back to SSH
            repo_url = f"git@github.com:{repo}.git"
            cloned_repo = git.Repo.clone_from(repo_url, clone_path)

        # Checkout the specified ref
        cloned_repo.git.checkout(ref)

        print(f"Cloned {repo} at {ref} to {clone_path}")


manager = DeploymentManager.configure(Path('/home/xieyt/frappe/sites/cicd.localhost/workspace/frappe-bench'))
