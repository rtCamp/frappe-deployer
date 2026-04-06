from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RemoteWorkerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    server_ip: str = Field(..., description="IP address or domain name of the remote server", min_length=1)
    ssh_user: Optional[str] = Field("frappe", description="SSH username for the remote server")
    ssh_port: Optional[int] = Field(22, description="SSH port number")
    include_dirs: Optional[List[str]] = Field(default_factory=list, description="Additional directories to sync")
    include_files: Optional[List[str]] = Field(default_factory=list, description="Additional files to sync")

    @property
    def fm_benches_path(self) -> str:
        return f"/home/{self.ssh_user}/frappe/sites"
