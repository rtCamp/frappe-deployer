from pydantic import BaseModel, Field
from typing import Optional

class RemoteWorkerConfig(BaseModel):
    """Configuration for remote worker settings

    Attributes:
        server_ip: str
            The IP address or domain name of the remote server
        ssh_user: str
            SSH username for connecting to the remote server (default: root)
        ssh_port: int
            SSH port number (default: 22)
        workspace_path: str
            Path on remote server where workspace will be synced (default: /home/frappe/frappe)
    """
    server_ip: str = Field(
        ..., 
        description="IP address or domain name of the remote server",
        min_length=1
    )
    ssh_user: Optional[str] = Field("frappe", description="SSH username for the remote server")
    ssh_port: Optional[int] = Field(22, description="SSH port number")
    include_dirs: Optional[list[str]] = Field(default_factory=list, description="List of additional directories to sync")
    include_files: Optional[list[str]] = Field(default_factory=list, description="List of additional files to sync")

    @property
    def fm_benches_path(self) -> str:
        """Get the workspace path for the remote server based on ssh user.
        
        Returns:
            str: The full path to the workspace directory
        """
        return f"/home/{self.ssh_user}/frappe/sites"
