from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ReleaseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    releases_retain_limit: int = Field(7, description="Number of releases to retain.")
    symlink_subdir_apps: bool = Field(
        False,
        description="Symlink all apps that have a subdir_path configured. Can be overridden per-app.",
    )
    mode: Optional[str] = Field(None, description="Runner mode: 'image' or 'exec'. Defaults to 'exec'.")
    python_version: Optional[str] = Field(None, description="Python version to bake into the release via uv.")
    node_version: Optional[str] = Field(None, description="Node.js version to bake into the release via fnm.")
    runner_image: str = Field(
        "",
        description="Docker image used to create releases. Auto-detected from installed frappe-manager version if empty.",
    )

    before_bench_build: Optional[str] = Field(
        None, description="Global fallback: script inside container before bench build."
    )
    after_bench_build: Optional[str] = Field(
        None, description="Global fallback: script inside container after bench build."
    )
    host_before_bench_build: Optional[str] = Field(
        None, description="Global fallback: script on host before bench build."
    )
    host_after_bench_build: Optional[str] = Field(
        None, description="Global fallback: script on host after bench build."
    )
    before_python_install: Optional[str] = Field(
        None, description="Global fallback: script inside container before pip install."
    )
    after_python_install: Optional[str] = Field(
        None, description="Global fallback: script inside container after pip install."
    )
    host_before_python_install: Optional[str] = Field(
        None, description="Global fallback: script on host before pip install."
    )
    host_after_python_install: Optional[str] = Field(
        None, description="Global fallback: script on host after pip install."
    )
