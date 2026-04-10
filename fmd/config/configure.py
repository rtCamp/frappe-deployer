from pydantic import BaseModel, ConfigDict, Field


class ConfigureConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backups: bool = Field(True, description="Take DB backup before configure.")
