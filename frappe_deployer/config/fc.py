from typing import Optional
from pydantic import BaseModel, Field
from pydantic import model_validator
from frappe_deployer.fc import FrappeCloudClient
from frappe_manager.logger.log import richprint

class FCConfig(BaseModel):
    """
    FCConfig is a Pydantic model representing the configuration for Frappe Cloud.

    Attributes
    ----------
    api_key : str
        Frappe Cloud API key. (Required)
    api_secret : str
        Frappe Cloud API secret. (Required)
    site_name : str
        Frappe Cloud Site Name. (Required)
    use_deps : Optional[bool]
        Use Frappe Cloud dependencies list (python version, node version, etc). Defaults to False.
    use_db : Optional[bool]
        Frappe Cloud Site Name to use for DB. Defaults to False.
    use_apps : Optional[bool]
        Enable Frappe Cloud Site Apps. Defaults to False.
    """

    api_key: str = Field(..., description="Frappe Cloud API key.")
    api_secret: str = Field(..., description="Frappe Cloud API secret.")
    site_name: str = Field(..., description="Frappe Cloud Site Name.")
    team_name: str = Field(..., description="Frappe Cloud Team Name.")
    use_deps: Optional[bool] = Field(False, description="Use Frappe Cloud dependencies list (python version, node version, etc).")
    use_db: Optional[bool] = Field(False, description="Frappe Cloud Site Name to use for DB.")
    use_apps: Optional[bool] = Field(False, description="Enable Frappe Cloud Site Apps.")

    @model_validator(mode="after")
    def validate_fc_credentials(cls, values):
        api_key = values.api_key
        api_secret = values.api_secret
        team_name = values.team_name
        site_name = values.site_name

        try:
            client = FrappeCloudClient(team_name, api_key, api_secret)
            resp = client.post("press.api.client.get", json={"doctype": "Site", "name": site_name})

            if resp.status_code != 200:
                raise ValueError("Invalid Frappe Cloud API key/secret or team name.")

            site_info = resp.json().get("message", {})
            group_name = site_info.get("group", "Unknown")

            richprint.print(
                f"[bold green]Frappe Cloud credentials validated![/bold green]\n"
                f"[bold]  Site Name:[/bold] {site_name}\n"
                f"[bold]  Team Name:[/bold] {team_name}\n"
                f"[bold]  Bench Group Name:[/bold] {group_name}",
                emoji_code=":cloud:"
            )

        except Exception as e:
            raise ValueError(f"Failed to validate Frappe Cloud credentials: {e}")

        return values
