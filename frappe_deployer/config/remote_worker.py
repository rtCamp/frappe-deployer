from pydantic import BaseModel, Field
from typing import Optional

class RemoteWorkerConfig(BaseModel):
    """Configuration for remote worker settings

    Attributes:
        server: str
            The IP address or domain name of the remote server
        ssh_user: str
            SSH username for connecting to the remote server (default: root)
        ssh_port: int
            SSH port number (default: 22)
        workspace_path: str
            Path on remote server where workspace will be synced (default: /home/frappe/frappe)
    """
    server: str = Field(
        ..., 
        description="IP address or domain name of the remote server",
        min_length=1
    )
    ssh_user: Optional[str] = Field("root", description="SSH username for the remote server")
    ssh_port: Optional[int] = Field(22, description="SSH port number")

    @property
    def fm_benches_path(self) -> str:
        """Get the workspace path for the remote server based on ssh user.
        
        Returns:
            str: The full path to the workspace directory
        """
        return f"/home/{self.ssh_user}/frappe/sites"
