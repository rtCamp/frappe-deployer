from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ShipConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str = Field(..., description="Server hostname or IP address")
    ssh_user: str = Field("frappe", description="SSH username for the remote server")
    ssh_port: int = Field(22, description="SSH port number")
    remote_path: Optional[str] = Field(
        None, description="Absolute path on remote server where the bench/workspace lives"
    )
    fmd_source: Optional[str] = Field(None, description="FMD source for uvx (git URL or local path)")
    rsync_options: List[str] = Field(default_factory=list, description="Extra rsync flags")
