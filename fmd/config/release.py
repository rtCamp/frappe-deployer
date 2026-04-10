from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ReleaseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Optional[str] = Field(None, description="Runner mode: 'image' or 'exec'. Defaults to 'exec'.")
    runner_image: Optional[str] = Field(
        None,
        description="Override Docker image for image mode. Auto-detects frappe-manager version if not set.",
    )
    platform: Optional[str] = Field(
        None,
        description="Docker platform for multi-arch images (e.g., 'linux/amd64', 'linux/arm64'). Auto-detected if not set.",
    )
    releases_retain_limit: int = Field(7, description="Number of releases to retain during cleanup.")
    symlink_subdir_apps: bool = Field(
        False,
        description="Symlink monorepo subdirectory apps instead of copying.",
    )
    mode: Optional[str] = Field(None, description="Runner mode: 'image' or 'exec'. Defaults to 'exec'.")
    python_version: Optional[str] = Field(None, description="Python version to bake into the release via uv.")
    node_version: Optional[str] = Field(None, description="Node.js version to bake into the release via fnm.")
    runner_image: str = Field(
        "",
        description="Docker image used to create releases. Auto-detected from installed frappe-manager version if empty.",
    )

    use_fc_apps: bool = Field(
        False,
        description="Import app list from Frappe Cloud. Overrides local [[apps]] refs with FC commit hashes.",
    )
    use_fc_deps: bool = Field(
        False,
        description="Import python_version from Frappe Cloud dependencies.",
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
