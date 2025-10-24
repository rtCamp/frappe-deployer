from dataclasses import dataclass
import json
import re
from typing import Optional
import git
from pathlib import Path

from frappe_deployer.config.app import AppConfig

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

    def setup_dir(self, create_tmps=False):
        self.sites.mkdir(parents=True,exist_ok=True)
        self.apps.mkdir(parents=True,exist_ok=True)
        self.logs.mkdir(parents=True,exist_ok=True)
        self.config.mkdir(parents=True,exist_ok=True)

        if create_tmps:
            config_pids = self.config / "pids"
            config_pids.mkdir(parents=True,exist_ok=True)

    def list_sites(self) -> list[Path]:
        """Returns a list of site names (directories) within the sites directory that are FQDNs."""

        if self.sites.exists() and self.sites.is_dir():
            return [
                site for site in self.sites.iterdir()
                if site.is_dir() and ( site / 'site_config.json').is_file()
            ]
        return []

    def clone(**kwargs):
        git.Repo.clone_from(**kwargs)

    def clone_app(self, app: AppConfig, clone_path: Path, move_to_subdir: bool = True) -> Path:
        import shutil

        clone_path_tmp = Path(str(clone_path) + "_tmp")

        # Clean up if the directory exists
        if clone_path_tmp.exists():
            shutil.rmtree(clone_path_tmp)

        clone_path_tmp.mkdir(parents=True, exist_ok=True)

        depth = 1 if app.shallow_clone else None

        if not app.is_ref_commit:
            cloned_repo = git.Repo.clone_from(
                app.repo_url, clone_path_tmp, depth=depth, origin=app.remote_name, branch=app.ref
            )
        else:
            cloned_repo = git.Repo.clone_from(
                app.repo_url, clone_path_tmp, depth=depth, origin=app.remote_name
            )

            if app.shallow_clone:
                cloned_repo.git.fetch('--depth', '1', app.remote_name, app.ref)

            cloned_repo.git.checkout(app.ref)

        move_path = clone_path_tmp

        if app.remove_remote:
            cloned_repo.delete_remote(cloned_repo.remote(app.remote_name))

        if app.subdir_path:
            if move_to_subdir:
                move_path = clone_path_tmp / app.subdir_path

        shutil.move(move_path, clone_path)

        if app.subdir_path:
            if move_to_subdir:
                shutil.rmtree(clone_path_tmp)

        return clone_path

    def maintenance_mode(self, site_name: str, value: bool = True):
        site_config = self.sites / site_name  / 'site_config.json'
        json_site_config = json.loads(site_config.read_text())
        json_site_config['maintenance_mode'] = int(value)
        site_config.write_text(json.dumps(json_site_config, indent=4))

    def get_frappe_bench_app_path(self, app: AppConfig, suffix: Optional[str] = None, append_release_name: Optional[str] = None) -> Path:
        app_path = self.apps

        if append_release_name:
            app_path = app_path / append_release_name

        return app_path / (app.dir_name + suffix if suffix else app.dir_name)


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
