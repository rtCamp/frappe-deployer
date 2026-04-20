from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PullConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ssh_server: str = Field(..., description="Server hostname or IP address")
    ssh_user: str = Field("frappe", description="SSH username for the remote server")
    ssh_port: int = Field(22, description="SSH port number")
    fmd_source: Optional[str] = Field(None, description="FMD source for uv install (git URL or local path)")
