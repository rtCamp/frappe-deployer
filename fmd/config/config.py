import concurrent.futures
import io
from pathlib import Path
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

try:
    from frappe_manager import CLI_BENCHES_DIRECTORY
except Exception:
    CLI_BENCHES_DIRECTORY = Path("/workspace")

try:
    import toml
except Exception:
    try:
        import tomllib as toml
    except Exception:
        import json as toml

from fmd.config.app import AppConfig
from fmd.config.bake import BakeConfig, BakeNginxConfig
from fmd.config.deploy import DeployConfig
from fmd.config.switch import SwitchConfig
from fmd.config.fc import FCConfig
from fmd.config.fm import FMConfig
from fmd.config.release import ReleaseConfig
from fmd.config.remote_worker import RemoteWorkerConfig
from fmd.config.ship import ShipConfig


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    _config_file_path: Optional[Path] = PrivateAttr(default=None)

    site_name: str = Field(..., description="The name of the site.")
    github_token: Optional[str] = Field(None, description="GitHub personal access token.")
    verbose: bool = Field(False, description="Enable verbose output.")
    uv: bool = Field(True, description="Use uv instead of pip.")

    apps: List[AppConfig] = Field(default_factory=list, description="List of application configurations.")

    release: ReleaseConfig = Field(default_factory=ReleaseConfig)
    switch: SwitchConfig = Field(default_factory=SwitchConfig)
    deploy: Optional[DeployConfig] = Field(None, description="DEPRECATED: Use [switch] instead.")

    bake: Optional[BakeConfig] = Field(None, description="Frappe image build configuration.")
    bake_nginx: Optional[BakeNginxConfig] = Field(None, description="Nginx image build configuration.")
    fm: Optional[FMConfig] = Field(None, description="FM integration configuration.")
    fc: Optional[FCConfig] = Field(None, description="Frappe Cloud configuration.")
    remote_worker: Optional[RemoteWorkerConfig] = Field(None, description="Remote worker configuration.")
    ship: Optional[ShipConfig] = Field(None, description="Ship deployment configuration.")

    @model_validator(mode="after")
    def _configure_apps(self) -> "Config":
        if self.deploy is not None:
            print("WARNING: [deploy] section is deprecated. Please rename to [switch] in your config.")
            if self.switch == SwitchConfig():
                deploy_data = self.deploy.model_dump()
                build_hooks = [
                    "before_bench_build",
                    "after_bench_build",
                    "host_before_bench_build",
                    "host_after_bench_build",
                    "before_python_install",
                    "after_python_install",
                    "host_before_python_install",
                    "host_after_python_install",
                ]
                for hook in build_hooks:
                    deploy_data.pop(hook, None)
                self.switch = SwitchConfig(**deploy_data)
            self.deploy = None

        for app in self.apps:
            if app.subdir_path:
                app.symlink = app.symlink or self.release.symlink_subdir_apps

        if not self.apps:
            return self

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(
                    app.configure_app,
                    token=self.github_token,
                    before_bench_build=app.before_bench_build or self.release.before_bench_build,
                    after_bench_build=app.after_bench_build or self.release.after_bench_build,
                    host_before_bench_build=app.host_before_bench_build or self.release.host_before_bench_build,
                    host_after_bench_build=app.host_after_bench_build or self.release.host_after_bench_build,
                    before_python_install=app.before_python_install or self.release.before_python_install,
                    after_python_install=app.after_python_install or self.release.after_python_install,
                    host_before_python_install=app.host_before_python_install
                    or self.release.host_before_python_install,
                    host_after_python_install=app.host_after_python_install or self.release.host_after_python_install,
                )
                for app in self.apps
            ]
            concurrent.futures.wait(futures)

        all_accessible = True
        for app in self.apps:
            if not app.exists:
                all_accessible = False
                print(f"Error: repo not accessible: {app.repo_url}")

        if not all_accessible:
            raise RuntimeError("Please ensure all app repos are accessible.")

        return self

    @property
    def bench_name(self) -> str:
        return self.bench_path.name

    @property
    def deploy_dir_path(self) -> Path:
        if self.ship and self._config_file_path is not None:
            return self._config_file_path.parent
        return CLI_BENCHES_DIRECTORY / self.site_name

    @property
    def bench_path(self) -> Path:
        return self.deploy_dir_path / "workspace" / "frappe-bench"

    def to_toml(self, file_path: Path) -> None:
        def _mask(data: Any) -> Any:
            if isinstance(data, dict):
                out = {}
                for k, v in data.items():
                    if k == "github_token" and v:
                        out[k] = "********"
                    elif k == "repo_url" and v and "@" in str(v):
                        parts = str(v).split("@")
                        protocol_token = parts[0].split("//")
                        out[k] = f"{protocol_token[0]}//*********@{parts[1]}"
                    else:
                        out[k] = _mask(v)
                return out
            elif isinstance(data, list):
                return [_mask(item) for item in data]
            return data

        config_dict = self.model_dump(exclude_none=True)
        masked = _mask(config_dict)

        with open(file_path, "w") as f:
            toml.dump(masked, f)

    @staticmethod
    def from_toml(
        config_file_path: Optional[Path] = None,
        config_string: Optional[str] = None,
        overrides: Optional[dict[str, Any]] = None,
    ) -> "Config":
        config_data: dict[str, Any] = {}

        if config_file_path:
            with open(config_file_path, "r") as f:
                config_data = toml.load(f)

        if config_string:
            with io.StringIO(config_string) as f:
                config_data = toml.load(f)

        if overrides:
            _NESTED_SECTIONS = {
                "bake",
                "bake_nginx",
                "deploy",
                "switch",
                "release",
                "fm",
                "fc",
                "ship",
                "remote_worker",
            }

            for key, value in overrides.items():
                if key in _NESTED_SECTIONS:
                    if isinstance(value, dict):
                        config_data[key] = config_data.get(key, {}) | value
                    else:
                        config_data[key] = value
                elif key == "apps":

                    def _app_key(app: dict) -> tuple:
                        return (app.get("repo", "").lower(), app.get("ref"), app.get("subdir_path"))

                    existing = {_app_key(a): a for a in config_data.get("apps", [])}
                    for app in value:
                        k = _app_key(app)
                        if k in existing:
                            merged = existing[k].copy()
                            merged.update(app)
                            existing[k] = merged
                        else:
                            existing[k] = app
                    config_data["apps"] = list(existing.values())
                elif key in Config.model_fields:
                    config_data[key] = value

        obj = Config(**config_data)
        if config_file_path:
            obj._config_file_path = config_file_path
        return obj
