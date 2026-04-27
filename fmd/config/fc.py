from pydantic import BaseModel, ConfigDict, Field


class FCConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key: str = Field(..., description="Frappe Cloud API key.")
    api_secret: str = Field(..., description="Frappe Cloud API secret.")
    site_name: str = Field(..., description="Frappe Cloud Site Name.")
    team_name: str = Field(..., description="Frappe Cloud Team Name.")
