from typing import Any, Optional
import requests

from frappe_deployer.config.app import AppConfig


class FrappeCloudClient:
    BASE_URL = "https://frappecloud.com/api/method"

    def __init__(self, team_name: str, api_key: str, api_secret: str):
        self.team_name = team_name
        self.api_key = api_key
        self.api_secret = api_secret
        self.headers = {
            "Authorization": f"Token {self.api_key}:{self.api_secret}",
            "X-Press-Team": self.team_name,
        }

    def get(self, endpoint: str, **kwargs) -> requests.Response:
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        return requests.get(url, headers=self.headers, **kwargs)

    def post(self, endpoint: str, json: Optional[dict] = None, **kwargs) -> requests.Response:
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        return requests.post(url, headers=self.headers, json=json, **kwargs)

    def _post_and_get_message(self, endpoint: str, data: dict) -> Any:
        """
        Helper to POST to an endpoint and return the 'message' field from the JSON response.
        """
        response = self.post(endpoint, json=data)
        result = response.json()
        return result.get("message", [])

    def get_bench_group(self, site_name: str) -> str:
        """
        Fetch the bench group for a given site name.
        """
        data = {"doctype": "Site", "name": site_name}
        response = self.post("press.api.client.get", json=data)
        result = response.json()
        site_info = result.get("message", {})
        return site_info.get("group")

    def get_dependencies(self, site_name: str) -> list[dict[str, Any]]:
        """
        Fetch the dependencies for a given Frappe Cloud site.
        """
        bench_group = self.get_bench_group(site_name)

        data = {
            "doctype": "Release Group Dependency",
            "fields": ["name", "dependency", "version"],
            "filters": {"parenttype": "Release Group", "parent": bench_group},
            "start": 0,
            "limit": 20,
            "limit_start": 0,
            "limit_page_length": 20,
            "debug": 0,
        }

        return self._post_and_get_message("press.api.client.get_list", data)

    def get_apps_list(self, site_name: str) -> list[dict[str, Any]]:
        """
        Fetch the list of apps for a given Frappe Cloud site.
        """
        data = {
            "doctype": "Site App",
            "fields": ["name", "repository", "repository_owner", "branch", "hash"],
            "filters": {"parenttype": "Site", "parent": site_name},
            "start": 0,
            "limit": 999,
            "limit_start": 0,
            "limit_page_length": 999,
            "debug": 0,
        }

        apps = self._post_and_get_message("press.api.client.get_list", data)

        filtered_apps = [
            {
                "name": app.get("name"),
                "app": app.get("app"),
                "repository": app.get("repository"),
                "repository_owner": app.get("repository_owner"),
                "branch": app.get("branch"),
                "hash": app.get("hash"),
            }
            for app in apps
        ]

        return filtered_apps

    def get_latest_backup_download_urls(self, site_name: str, files: list[str] = ["database"]) -> dict[str, str]:
        """
        Get download URLs for the latest backup files for the given site and file types.

        Args:
            site_name (str): The site name.
            files (list[str]): List of file types to fetch URLs for (e.g., ['database', 'public', 'private']).

        Returns:
            dict[str, str]: Mapping of file type to download URL.
        """
        # Step 1: Get the latest successful backup
        #
        data = {
            "doctype": "Site Backup",
            "fields": [
                "name",
                "job",
                "status",
                "database_url",
                "public_url",
                "private_url",
                "config_file_url",
                "site",
                "remote_database_file",
                "remote_public_file",
                "remote_private_file",
                "remote_config_file",
                "physical",
                "creation",
                "status",
                "database_size",
                "public_size",
                "private_size",
                "with_files",
                "offsite",
                "physical",
            ],
            "filters": { "offsite": True, "site": site_name, "status": ["in", ["Success"]]},
            "order_by": "creation desc",
            "start": 0,
            "limit": 1,
            "limit_start": 0,
            "limit_page_length": 1,
            "debug": 0,
        }

        backups = self._post_and_get_message("press.api.client.get_list", data)

        if not backups:
            raise ValueError(f"No backups found for site {site_name}")

        backup = backups[0]
        backup_name = backup["name"]

        # Step 2: For each file type, get the download URL
        urls = {}
        for filetype in files:
            payload = {
                "dt": "Site",
                "dn": site_name,
                "method": "get_backup_download_link",
                "args": {
                    "backup": backup_name,
                    "file": filetype
                }
            }
            resp = self.post("press.api.client.run_doc_method", json=payload)

            if resp.status_code == 200:
                result = resp.json()
                url = result.get("message", {})
                if url:
                    urls[filetype] = url
            else:
                urls[filetype] = None  # Or handle error as needed
        return urls


def fc_app_to_appconfig(app: dict[str, Any]):
    return {"ref": app.get("hash"), "repo": f"{app.get('repository_owner')}/{app.get('repository')}"}


def fc_apps_list_to_appconfig_list(apps: list[dict[str, Any]]):
    apps_list = [AppConfig(**fc_app_to_appconfig(app)) for app in apps]
    return apps_list
