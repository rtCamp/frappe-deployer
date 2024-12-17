from pathlib import Path
from typing import Any, List, Literal, Optional

from frappe_manager import CLI_BENCHES_DIRECTORY
from frappe_manager.utils.site import richprint
from pydantic import BaseModel, Field, field_validator, model_validator
from unittest.mock import patch
import toml

from frappe_deployer.config.app import AppConfig
from frappe_deployer.config.fm import FMConfig
from frappe_deployer.config.host import HostConfig

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
    site_name: str = Field(..., description="The name of the site.")
    github_token: Optional[str] = Field(None, description="The GitHub personal access token.")
    remove_remote: Optional[bool] = Field(False, description="Flag to remove the remote to cloned apps.")
    apps: List[AppConfig] = Field(..., description="List of application configurations.")
    python_version: Optional[str] = Field(None, description="Python Version to for venv creation.")
    run_bench_migrate: bool = Field(True, description="Flag to run bench migrate.")
    rollback: bool = Field(False, description="Allow rollback")
    maintenance_mode: bool = Field(True, description='Flag to use maintenance mode while restart and bench migrate and bench install-app.')
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
    host: Optional[HostConfig] = Field(None, description="Host configuration.")
    fm: Optional[FMConfig] = Field(None, description="FM configuration.")

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

        app: AppConfig

        for app in config.apps:
            app.configure_app(token=config.github_token,remove_remote=config.remove_remote)

        all_apps_exists = True

        for app in config.apps:
            if not app.exists:

                all_apps_exists = False
                richprint.error(app.repo_url)

        if not all_apps_exists:
            raise RuntimeError("Please ensure all apps repo's are accessible.")

        return config


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
        config_dict = self.model_dump(exclude_none=True)
        if config_dict.get('github_token'):
            config_dict['github_token'] = 'XXXXXXXXXXXXX'
        with open(file_path, 'w') as f:
            toml.dump(config_dict, f)

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
            # Merge overrides into config_data only if the keys are data members of Config
            for key, value in overrides.items():
                if key == 'apps':
                    # Handle the merging of apps
                    existing_apps = {app['repo']: app for app in config_data.get('apps', [])}

                    for app in value:
                        if app['repo'] in existing_apps:
                            existing_apps[app['repo']].update(app)
                        else:
                            existing_apps[app['repo']] = app

                    config_data['apps'] = list(existing_apps.values())
                    continue

                if key in Config.__fields__:
                    config_data[key] = value

        config = Config(**config_data)
        return config
