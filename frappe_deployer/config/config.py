import toml
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
from typing import List, Literal, Optional
from frappe_manager import CLI_BENCHES_DIRECTORY

from frappe_manager.display_manager.DisplayManager import richprint

from frappe_deployer.config.app import AppConfig
from frappe_deployer.config.host import HostConfig
from frappe_deployer.config.fm import FMConfig

class Config(BaseModel):
    site_name: str
    apps: List[AppConfig]
    maintenance_mode: bool = Field(True)
    mode: Literal['host', 'fm'] = Field(...)
    host: Optional[HostConfig] = None
    fm: Optional[FMConfig] = None

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


    @property
    def deploy_dir_path(self) -> Path:
        return self.bench_path.parent

    @field_validator('mode')
    def validate_mode(cls, v):
        if v not in ('host', 'fm'):
            raise ValueError('mode must be either "host" or "fm"')
        return v

    @field_validator('apps')
    def validate_apps(cls, v):
        apps_exists = True

        for app in v:
            if app.exists:
                richprint.print(f"Repo: [green]{app.repo}[/green] with ref '{app.ref}' is accessible. App url [blue]{app.repo_url}[/blue]")
            else:
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
