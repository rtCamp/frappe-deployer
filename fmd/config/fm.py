from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class FMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    restore_db_from_site: Optional[str] = Field(None)
