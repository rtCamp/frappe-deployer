import json
from pathlib import Path
from typing import Any, List, Literal, Optional, Union

from frappe_manager import CLI_BENCHES_DIRECTORY
from frappe_manager.utils.site import richprint
from pydantic import BaseModel, Field, field_validator, model_validator
from unittest.mock import patch
import toml

from frappe_deployer.config.app import AppConfig
from frappe_deployer.config.build import BuildConfig
from frappe_deployer.config.fc import FCConfig
from frappe_deployer.config.fm import FMConfig
from frappe_deployer.config.host import HostConfig
from frappe_deployer.config.remote_worker import RemoteWorkerConfig
from frappe_deployer.fc import FrappeCloudClient, fc_apps_list_to_appconfig_list

def patched_change_head(original_function):
    def wrapper(*args, **kwargs):
        result = original_function(*args, **kwargs)
        richprint.print(*args, emoji_code=':construction:')
        return result
    return wrapper

class Config(BaseModel):
    """
    Configuration file model

    Attributes
    ----------
    site_name : str
        The name of the site.
    github_token : Optional[str]
        The GitHub personal access token.
    remove_remote : Optional[bool]
        Flag to remove the remote to cloned apps.
    apps : List[AppConfig]
        List of application configurations.
    run_bench_migrate : bool
        Flag to run bench migrate.
    maintenance_mode : bool
        Flag to use maintenance mode while restart and bench migrate and bench install-app.
    releases_retain_limit : Optional[int]
        Number of releases to retain.
    reset_site : bool
        Flag to reset the site.
    common_site_config : Optional[dict[str, Any]]
        Common site configuration dictionary.
    site_config : Optional[dict[str, Any]]
        Site-specific configuration dictionary.
    restore_db_file_path : Optional[Path]
        Path to the database file to restore.
    maintenance_mode : bool
        Flag to enable maintenance mode.
    verbose : bool
        Flag to enable verbose output.
    uv : bool
        Flag to enable UV mode.
    mode : Literal['host', 'fm']
        Mode of operation, either 'host' or 'fm'.
    host : Optional[HostConfig]
        Host configuration.
    fm : Optional[FMConfig]
        FM configuration.
    """
    site_name: Optional[str] = Field(None, description="The name of the site.")
    github_token: Optional[str] = Field(None, description="The GitHub personal access token.")
    remove_remote: Optional[bool] = Field(True, description="Flag to remove the remote to cloned apps.")
    remote_name: Optional[str] = Field("upstream", description="Name of the remote to use during cloning")
    apps: List[AppConfig] = Field(..., description="List of application configurations.")
    python_version: Optional[str] = Field(None, description="Python Version to for venv creation.")
    node_version: Optional[str] = Field(None, description="Node.js Version to use.")
    run_bench_migrate: bool = Field(True, description="Flag to run bench migrate.")
    migrate_timeout: int = Field(600, description="Migrate timeout")
    wait_workers: bool = Field(False, description="Wait workers")
    wait_workers_timeout: int = Field(600, description="Wait workers timout")
    symlink_subdir_apps: bool = Field(
        False,
        description="Allow symlinking for all apps with subdirectory configuration; can be overridden by per-app symlink setting."
    )
    rollback: bool = Field(False, description="Allow rollback")
    maintenance_mode: bool = Field(True, description='Flag to use maintenance mode while restart and bench migrate and bench install-app.')
    maintenance_mode_phases: List[str] = Field(["migrate","start"], description='Phases in which maintenance mode will be active')
    backups: bool = Field(True, description="Flag to enable or disable backups.")
    configure: bool = Field(False, description="Flag to enable or disable site configuration for deployment.")
    releases_retain_limit: int = Field(7, description="Number of releases to retain.")
    reset_site: bool = Field(False, description="Flag to reset the site.")
    common_site_config: Optional[dict[str, Any]] = Field(None, description="Common site configuration dictionary.")
    site_config: Optional[dict[str, Any]] = Field(None, description="Site-specific configuration dictionary.")
    mode: Literal['host', 'fm'] = Field(..., description="Mode of operation, either 'host' or 'fm'.")
    restore_db_file_path: Optional[Path] = Field(None, description="Path to the database file to restore.")
    verbose: bool = Field(False, description="Flag to use 'uv' instead of 'pip' to manage and install packages.")
    uv: bool = Field(True, description="Flag to enable UV mode.")
    search_replace: bool = Field(True, description="Flag to enable search and replace in database.")
    host_pre_script: Optional[str] = Field(None, description="Script to run before bench migrate in host mode")
    host_post_script: Optional[str] = Field(None, description="Script to run after bench migrate in host mode") 
    fm_pre_script: Optional[str] = Field(None, description="Script to run before bench migrate in FM mode")
    fm_post_script: Optional[str] = Field(None, description="Script to run after bench migrate in FM mode")
    fm_pre_build: Optional[str] = Field(None, description="Script to run before building each app in FM mode")
    fm_post_build: Optional[str] = Field(None, description="Script to run after building each app in FM mode")
    host: Optional[HostConfig] = Field(None, description="Host configuration.")
    build: Optional[BuildConfig] = Field(None, description="Build configuration.")
    fm: Optional[FMConfig] = Field(None, description="FM configuration.")
    fc: Optional[FCConfig] = Field(None, description="FC configuration.")
    remote_worker: Optional[RemoteWorkerConfig] = Field(None, description="Remote worker configuration.")
    sync_workers: Optional[bool] = Field(False, description="Flag to sync to remote workers. Effective only if `remote_worker.server_ip` is configured.")

    @field_validator('restore_db_file_path',mode='before')
    def validate_db_file_path(cls, value, values):
        mode = values.data.get('mode', None)

        if not mode == 'fm':
            raise RuntimeError(f"Restore db feature not supported in 'host' mode. Please check config")

        path = Path(value)

        if not path.exists():
            raise ValueError(f"{path} file doesn't exists")

        return path

    @field_validator('verbose',mode='before')
    def validate_verbose(cls, value):

        if value:
            patcher = patch.object(richprint, 'change_head', new=patched_change_head(richprint.change_head))
            patcher.start()

        return value

    @property
    def bench_path(self) -> Path:
        if self.build:
            if not self.build.bench_path:
                raise ValueError("Host configuration is required when mode is 'host'")
            return self.build.bench_path

        if self.mode == 'fm':
            return CLI_BENCHES_DIRECTORY / self.site_name / 'workspace' / 'frappe-bench'

        if self.host is None:
            raise ValueError("Host configuration is required when mode is 'host'")

        return self.host.bench_path

    @property
    def bench_name(self) -> str:
        return self.bench_path.name

    @model_validator(mode='after')
    def configure_config(cls, config: Any) -> Any:
        FC_SPECIFIC_CONFIG_NAMES_TO_REMOVE = ["host_name", "plan_limit", "rate_limit", "ic_api_secret", "domains"]

        # add apps from fc
        if cls.fc:
            client = FrappeCloudClient(cls.fc.team_name,cls.fc.api_key,cls.fc.api_secret)

            urls = client.get_latest_backup_download_urls(cls.fc.site_name)
            if urls:
                from frappe_deployer.utils.download import download_file_with_progress
                download_status = download_file_with_progress(urls, dest_dir=Path("/tmp"))

                db = download_status.get("database",None)
                site_config = download_status.get("config",None)

                if cls:
                    if not cls.site_config or not cls.site_config.get("encryption_key", None):

                        if site_config:
                            site_config_path = site_config.get("absolute_path", None)

                            if site_config_path and Path(site_config_path).exists():
                                fc_site_config = json.loads(Path(site_config_path).read_text())

                                for name in FC_SPECIFIC_CONFIG_NAMES_TO_REMOVE:
                                    fc_site_config.pop(name)

                                cls.site_config = fc_site_config


                                richprint.print(f"Appended FC site_config.json keys")

                if db:
                    if not cls.restore_db_file_path:
                        db_path  = Path(db.get("absolute_path", None))
                        if db_path and db_path.exists():
                            cls.restore_db_file_path = db_path
                            richprint.print(f"FC db backup path: {db_path}")

            if cls.fc.use_deps:
                deps = client.get_dependencies(cls.fc.site_name)
                # Extract versions from deps
                python_version = next((d["version"] for d in deps if d["dependency"] == "PYTHON_VERSION"), None)
                # node_version = next((d["version"] for d in deps if d["dependency"] == "NODE_VERSION"), None)

                # Set config values if not already set
                if not getattr(cls, "python_version", None) and python_version:
                    cls.python_version = python_version

                # if not getattr(config, "node_version", None) and node_version:
                #     config.node_version = node_version

            if cls.fc.use_apps:
                fc_apps = fc_apps_list_to_appconfig_list(client.get_apps_list(cls.fc.site_name))

                # Create a mapping from repo (lowercase) to AppConfig for config.apps
                config_apps_map = {app.repo.lower(): app for app in cls.apps}

                # Merge: if app exists in config.apps, use it; else, use from fc_apps
                merged_apps = []
                fc_apps_map = {app.repo.lower(): app for app in fc_apps}
                all_repos = set(config_apps_map.keys()) | set(fc_apps_map.keys())

                for repo in all_repos:
                    if repo in config_apps_map and repo in fc_apps_map:
                        # Merge: config_apps_map[repo] overwrites fc_apps_map[repo]
                        merged_app_dict = fc_apps_map[repo].model_dump()
                        merged_app_dict.update(config_apps_map[repo].model_dump(exclude_unset=True))
                        merged_apps.append(AppConfig(**merged_app_dict))
                    elif repo in config_apps_map:
                        merged_apps.append(config_apps_map[repo])
                    else:
                        merged_apps.append(fc_apps_map[repo])

                cls.apps = merged_apps

        app: AppConfig

        for app in cls.apps:
            if getattr(app, "subdir_path", None):
                app.symlink = getattr(app, "symlink", False) or getattr(cls, "symlink_subdir_apps", False)

        for app in cls.apps:
            app.configure_app(
                token=cls.github_token,
                remove_remote=cls.remove_remote,
                remote_name=cls.remote_name,
                fm_pre_build=app.fm_pre_build or cls.fm_pre_build,
                fm_post_build=app.fm_post_build or cls.fm_post_build
            )

        all_apps_exists = True

        for app in cls.apps:
            if not app.exists:

                all_apps_exists = False
                richprint.error(app.repo_url)

        if not all_apps_exists:
            raise RuntimeError("Please ensure all apps repo's are accessible.")

        return cls


    @property
    def deploy_dir_path(self) -> Path:
        return self.bench_path.parent

    @field_validator('mode')
    def validate_mode(cls, v):
        if v not in ('host', 'fm'):
            raise ValueError('mode must be either "host" or "fm"')
        return v

    def to_toml(self, file_path: Path) -> None:
        """
        Dumps the configuration to a TOML file.

        Parameters
        ----------
        file_path : Path
            The path where to save the TOML file.
        """
        def mask_sensitive_data(data: Any) -> Any:
            """Recursively mask sensitive data in config"""
            if isinstance(data, dict):
                masked_data = {}
                for k, v in data.items():
                    if k == "github_token" and v:
                        masked_data[k] = "********"
                    elif k == "repo_url" and v and "@" in v:
                        # Mask token in URLs like https://token@github.com/...
                        parts = v.split('@')
                        protocol_token = parts[0].split('//')
                        masked_data[k] = f"{protocol_token[0]}//*********@{parts[1]}"
                    else:
                        masked_data[k] = mask_sensitive_data(v)
                return masked_data
            elif isinstance(data, list):
                return [mask_sensitive_data(item) for item in data]
            return data

        config_dict = self.model_dump(exclude_none=True)
        masked_config = mask_sensitive_data(config_dict)

        with open(file_path, 'w') as f:
            toml.dump(masked_config, f)

    @staticmethod 
    def from_toml(config_file_path: Optional[Path] = None, config_string: Optional[str] = None, overrides: Optional[dict[str, Any]] = None ) -> 'Config':
        config_data = {}

        if config_file_path:
            with open(config_file_path, 'r') as file:
                config_data = toml.load(file)

        if config_string:
            import io
            with io.StringIO(config_string) as f:
                config_data = toml.load(f)

        if overrides:
            for key, value in overrides.items():
                if key == 'apps':
                    # Use (repo.lower(), ref, subdir_path or None) as the unique key
                    def app_key(app):
                        return (
                            app.get('repo', '').lower(),
                            app.get('ref', None),
                            app.get('subdir_path', None)
                        )

                    existing_apps = {app_key(app): app for app in config_data.get('apps', [])}

                    for app in value:
                        k = app_key(app)
                        if k in existing_apps:
                            merged_app = existing_apps[k].copy()
                            merged_app.update(app)
                            existing_apps[k] = merged_app
                        else:
                            existing_apps[k] = app

                    config_data['apps'] = list(existing_apps.values())
                    continue

                if key in Config.model_fields:
                    config_data[key] = value

        config = Config(**config_data)
        return config
