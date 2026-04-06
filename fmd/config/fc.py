from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class FCConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key: str = Field(..., description="Frappe Cloud API key.")
    api_secret: str = Field(..., description="Frappe Cloud API secret.")
    site_name: str = Field(..., description="Frappe Cloud Site Name.")
    team_name: str = Field(..., description="Frappe Cloud Team Name.")
    use_deps: bool = Field(False, description="Set python_version from FC dependencies.")
    use_db: bool = Field(False, description="Download latest FC backup and restore at switch time.")
    use_apps: bool = Field(False, description="Merge FC app list into Config.apps (replaces [[apps]]).")
