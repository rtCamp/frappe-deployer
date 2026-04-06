from pydantic import BaseModel, ConfigDict, Field


class ReleaseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    releases_retain_limit: int = Field(7, description="Number of releases to retain.")
    symlink_subdir_apps: bool = Field(
        False,
        description="Symlink all apps that have a subdir_path configured. Can be overridden per-app.",
    )
