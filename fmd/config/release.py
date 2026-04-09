from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ReleaseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    releases_retain_limit: int = Field(7, description="Number of releases to retain.")
    symlink_subdir_apps: bool = Field(
        False,
        description="Symlink all apps that have a subdir_path configured. Can be overridden per-app.",
    )
    python_version: Optional[str] = Field(None, description="Python version to bake into the release via uv.")
    node_version: Optional[str] = Field(None, description="Node.js version to bake into the release via fnm.")
    runner_image: str = Field(
        "",
        description="Docker image used to create releases. Auto-detected from installed frappe-manager version if empty.",
    )
