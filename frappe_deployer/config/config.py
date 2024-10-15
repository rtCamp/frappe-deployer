from pathlib import Path
from typing import Any, List, Literal, Optional

from frappe_manager import CLI_BENCHES_DIRECTORY
from frappe_manager.utils.site import richprint
from pydantic import BaseModel, Field, field_validator
import toml

from frappe_deployer.config.app import AppConfig
from frappe_deployer.config.fm import FMConfig
from frappe_deployer.config.host import HostConfig

class Config(BaseModel):
    site_name: str
    apps: List[AppConfig]
    releases_retain_limit: int
    common_site_config: Optional[dict[str,Any]] = None
    site_config: Optional[dict[str,Any]] = None
    restore_db_file_path: Optional[Path] = None
    restore_db_encryption_key: Optional[str] = None
    maintenance_mode: bool = Field(True)
    verbose: bool = Field(False)
    uv: bool = Field(True)
    mode: Literal['host', 'fm'] = Field(...)
    host: Optional[HostConfig] = None
    fm: Optional[FMConfig] = None

    @field_validator('releases_retain_limit',mode='before')
    def validate_releases_retain_limit(cls, value):
        if not value:
            value = 7
        return value

    @field_validator('restore_db_file_path',mode='before')
    def validate_db_file_path(cls, value, values):
        mode = values.data.get('mode')
        print(mode)
        if not mode == 'fm':
            raise RuntimeError(f"Restore db feature not supported in 'host' mode. Please check config")

        path = Path(value)

        if not path.exists():
            raise ValueError(f"{path} file doesn't exists")

        return path

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

    @field_validator('apps',mode='before')
    def initialize_apps(cls, values):
        apps = []
        for app in values:
            apps.append(AppConfig.from_dict(app))
        return apps

    @property
    def deploy_dir_path(self) -> Path:
        return self.bench_path.parent

    @field_validator('mode')
    def validate_mode(cls, v):
        if v not in ('host', 'fm'):
            raise ValueError('mode must be either "host" or "fm"')
        return v

    @field_validator('apps', mode='after')
    def validate_apps(cls, v):
        apps_exists = True

        for app in v:
            if not app.exists:
                apps_exists = False
                richprint.error(app.repo_url)

        if not apps_exists:
            richprint.exit("Please ensure all apps repo's are accessible.")

        return v

    @staticmethod
    def from_toml(file_name: str) -> 'Config':
        with open(file_name, 'r') as file:
            config_data = toml.load(file)
        return Config(**config_data)
