import concurrent.futures
import contextvars
import io
import os
import re
from pathlib import Path
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

try:
    from frappe_manager import CLI_BENCHES_DIRECTORY
except Exception:
    # Check for bare host deployment via environment variable
    if os.environ.get("FMD_BARE_HOST") == "1":
        benches_root = os.environ.get("FMD_HOST_BENCHES_ROOT", "/home/frappe/frappe/sites")
        CLI_BENCHES_DIRECTORY = Path(benches_root)
    else:
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
from fmd.config.configure import ConfigureConfig
from fmd.config.deploy import DeployConfig
from fmd.config.switch import SwitchConfig
from fmd.config.fc import FCConfig
from fmd.config.fm import FMConfig
from fmd.config.pull import PullConfig
from fmd.config.release import ReleaseConfig
from fmd.config.remote_worker import RemoteWorkerConfig
from fmd.config.ship import ShipConfig

# Context variable to control repo validation during Config construction
_skip_repo_validation_context: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_skip_repo_validation_context", default=False
)


def _substitute_env_vars(data: Any) -> Any:
    """
    Recursively substitute environment variables in config data.
    Supports ${VAR_NAME} and $VAR_NAME syntax.
    """
    if isinstance(data, dict):
        return {key: _substitute_env_vars(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_substitute_env_vars(item) for item in data]
    elif isinstance(data, str):

        def replace_var(match):
            var_name = match.group(1) or match.group(2)
            return os.environ.get(var_name, match.group(0))

        pattern = r"\$\{([A-Z_][A-Z0-9_]*)\}|\$([A-Z_][A-Z0-9_]*)"
        return re.sub(pattern, replace_var, data)
    else:
        return data


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    _config_file_path: Optional[Path] = PrivateAttr(default=None)
    _skip_repo_validation: bool = PrivateAttr(default=False)

    site_name: str = Field(..., description="The name of the site.")
    bench_name: Optional[str] = Field(None, description="The bench/container identifier. Defaults to site_name.")
    github_token: Optional[str] = Field(None, description="GitHub personal access token.")
    verbose: bool = Field(False, description="Enable verbose output.")

    apps: List[AppConfig] = Field(default_factory=list, description="List of application configurations.")

    release: ReleaseConfig = Field(default_factory=ReleaseConfig)
    switch: SwitchConfig = Field(default_factory=SwitchConfig)
    configure: ConfigureConfig = Field(default_factory=ConfigureConfig)
    deploy: Optional[DeployConfig] = Field(None, description="DEPRECATED: Use [switch] instead.")

    bake: Optional[BakeConfig] = Field(None, description="Frappe image build configuration.")
    bake_nginx: Optional[BakeNginxConfig] = Field(None, description="Nginx image build configuration.")
    fm: Optional[FMConfig] = Field(None, description="FM integration configuration.")
    fc: Optional[FCConfig] = Field(None, description="Frappe Cloud configuration.")
    remote_worker: Optional[RemoteWorkerConfig] = Field(None, description="Remote worker configuration.")
    pull: Optional[PullConfig] = Field(None, description="Pull deployment configuration.")
    ship: Optional[ShipConfig] = Field(None, description="Ship deployment configuration.")

    @model_validator(mode="after")
    def _configure_apps(self) -> "Config":
        skip_validation = _skip_repo_validation_context.get()

        if self.bench_name is None:
            self.bench_name = self.site_name

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

        if not skip_validation:
            all_accessible = True
            for app in self.apps:
                if not app.exists:
                    all_accessible = False
                    from fmd.config.utils import richprint

                    richprint.print(f"Error: repo not accessible: {app.repo_url}")

            if not all_accessible:
                raise RuntimeError("Please ensure all app repos are accessible.")

        return self

    @property
    def workspace_root(self) -> Path:
        if self.ship and self._config_file_path is not None:
            return self._config_file_path.parent

        assert self.bench_name is not None

        if self.pull and self.pull.benches_root:
            return Path(self.pull.benches_root) / self.bench_name

        return CLI_BENCHES_DIRECTORY / self.bench_name

    @property
    def bench_path(self) -> Path:
        if self.ship and self._config_file_path is not None:
            return self.workspace_root / "workspace" / "frappe-bench"
        return self.workspace_root / "workspace" / "frappe-bench"

    def to_toml(self, file_path: Path, mask_secrets: bool = True) -> None:
        def _mask(data: Any) -> Any:
            if isinstance(data, dict):
                out = {}
                for k, v in data.items():
                    if mask_secrets and k == "github_token" and v:
                        out[k] = "********"
                    elif mask_secrets and k == "repo_url" and v and "@" in str(v):
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

        if mask_secrets:
            config_dict = _mask(config_dict)

        with open(file_path, "w") as f:
            toml.dump(config_dict, f)

    @staticmethod
    def from_toml(
        config_file_path: Optional[Path] = None,
        config_string: Optional[str] = None,
        overrides: Optional[dict[str, Any]] = None,
        skip_repo_validation: bool = False,
    ) -> "Config":
        token = _skip_repo_validation_context.set(skip_repo_validation)
        try:
            config_data: dict[str, Any] = {}

            if config_file_path:
                with open(config_file_path, "r") as f:
                    config_data = toml.load(f)

            if config_string:
                with io.StringIO(config_string) as f:
                    config_data = toml.load(f)

            config_data = _substitute_env_vars(config_data)

            if overrides:
                _NESTED_SECTIONS = {
                    "bake",
                    "bake_nginx",
                    "configure",
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
            obj._skip_repo_validation = skip_repo_validation
            if config_file_path:
                obj._config_file_path = config_file_path
            return obj
        finally:
            _skip_repo_validation_context.reset(token)
