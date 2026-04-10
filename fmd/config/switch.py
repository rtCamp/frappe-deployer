from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SwitchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    migrate: bool = Field(True, description="Run bench migrate.")
    migrate_timeout: int = Field(300, description="Migrate timeout in seconds.")
    migrate_command: Optional[str] = Field(None, description="Custom migrate command override.")
    maintenance_mode: bool = Field(True, description="Enable maintenance mode during restart/migrate/install.")
    maintenance_mode_phases: List[str] = Field(
        default_factory=list,
        description="Phases in which maintenance mode is active: 'drain' and/or 'migrate'.",
    )
    backups: bool = Field(True, description="Take DB backup before switch.")
    rollback: bool = Field(False, description="Roll back to previous release on failure.")
    search_replace: bool = Field(True, description="Run search-and-replace in DB after restore.")
    sync_workers: bool = Field(False, description="Sync to remote workers after deploy.")
    use_fc_db: bool = Field(False, description="Download and restore latest Frappe Cloud backup at switch time.")

    drain_workers: bool = Field(False, description="Drain workers before restart.")
    drain_workers_timeout: int = Field(300, description="Seconds to wait for workers to drain.")
    drain_workers_poll: int = Field(5, description="Poll interval in seconds while draining.")
    skip_stale_workers: bool = Field(True, description="Skip stale workers when draining.")
    skip_stale_timeout: int = Field(15, description="Seconds before a worker is considered stale.")
    worker_kill_timeout: int = Field(15, description="Seconds before force-killing workers.")
    worker_kill_poll: float = Field(3.0, description="Poll interval in seconds while waiting to kill workers.")

    common_site_config: Optional[dict[str, Any]] = Field(
        None, description="Keys to merge into common_site_config.json."
    )
    site_config: Optional[dict[str, Any]] = Field(None, description="Keys to merge into site_config.json.")

    before_restart: Optional[str] = Field(None, description="Script inside container before restart.")
    after_restart: Optional[str] = Field(None, description="Script inside container after restart.")
    host_before_restart: Optional[str] = Field(None, description="Script on host before restart.")
    host_after_restart: Optional[str] = Field(None, description="Script on host after restart.")
