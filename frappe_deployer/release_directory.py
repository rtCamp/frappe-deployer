from dataclasses import dataclass
import json
import re
import git
from pathlib import Path

from frappe_deployer.config.app import AppConfig
from frappe_deployer.helpers import is_fqdn as fqdn

@dataclass
class BenchDirectory:
    path: Path

    @property
    def is_configured(self) -> bool:
        return self.path.is_symlink()

    @property
    def logs(self) -> Path:
        return self.path / 'logs'

    @property
    def config(self) -> Path:
        return self.path / 'config'

    @property
    def apps(self) -> Path:
        return self.path / 'apps'

    @property
    def sites(self) -> Path:
        return self.path / 'sites'

    @property
    def env(self) -> Path:
        return self.path / 'env'

    @property
    def common_site_config(self) -> Path:
        return self.sites / 'common_site_config.json'

    @property
    def nginx_conf(self) -> Path:
        return self.config / 'nginx.conf'

    def setup_dir(self):
        self.sites.mkdir(parents=True,exist_ok=True)
        self.apps.mkdir(parents=True,exist_ok=True)
        self.logs.mkdir(parents=True,exist_ok=True)
        self.config.mkdir(parents=True,exist_ok=True)

    def list_sites(self) -> list[Path]:
        """Returns a list of site names (directories) within the sites directory that are FQDNs."""
        if self.sites.exists() and self.sites.is_dir():
            return [
                site for site in self.sites.iterdir()
                if site.is_dir() and fqdn(site.name)
            ]
        return []

    def clone(**kwargs):
        git.Repo.clone_from(**kwargs)

    def clone_app(self, app: AppConfig):
        """
        Clone a specific ref (tag/branch/commit) from a GitHub repository.

        :param repo: The repository in the format <owner>/<repo>, e.g., frappe/frappe.
        :param ref: The ref to checkout, can be a tag, branch, or commit.
        :param clone_path: The path where the repository should be cloned.
        :param token: Optional GitHub user token for HTTPS authentication.
        """

        clone_path = self.get_app_path(app)

        #TODO: Check moving the directory to the app's python modoule name

        depth = 1

        if not app.shallow_clone:
            depth = None

        # progress = CloneProgress()

        if not app.is_ref_commit:
            cloned_repo = git.Repo.clone_from(app.repo_url, clone_path, depth=depth,branch=app.ref)
        else:
            cloned_repo = git.Repo.clone_from(app.repo_url, clone_path, depth=depth)
            if app.shallow_clone:
                cloned_repo.git.fetch('--depth', '1', 'origin', app.ref)

            cloned_repo.git.checkout(app.ref)

    def maintenance_mode(self, site_name: str, value: bool = True):
        site_config = self.sites / site_name  / 'site_config.json'
        json_site_config = json.loads(site_config.read_text())
        json_site_config['maintenance_mode'] = int(value)
        site_config.write_text(json.dumps(json_site_config, indent=4))

    def get_app_path(self, app: AppConfig) -> Path:
        return self.apps / app.dir_name

    def get_app_python_module_name(self, app_path: Path):
        if not app_path.exists():
            return app_path.name

        hooks_py_files = app_path.glob('*/**/hooks.py')

        try:
            file_path = next(path for path in hooks_py_files if len(path.relative_to(app_path).parts) <= 2)
        except StopIteration:
            raise RuntimeError(f"Cannot file hooks.py file in {app_path} dir")

        # Use regex to find the app_name
        match = re.search(r'app_name\s*=\s*"(.*?)"', file_path.read_text())
        if not match:
            raise RuntimeError(f'Cannot determine python module name in {app_path} dir')

        app_name = match.group(1)  # Extract the value

        return app_name
