from pathlib import Path
from typing import Optional

try:
    import requests as _requests
except Exception:
    _requests = None

from fmd.config.app import AppConfig
from fmd.config.fc import FCConfig
from fmd.fc.client import FrappeCloudClient, fc_apps_list_to_appconfig_list


class FCDataSource:
    def __init__(self, config: FCConfig):
        self._config = config
        self._client = FrappeCloudClient(
            team_name=config.team_name,
            api_key=config.api_key,
            api_secret=config.api_secret,
        )

    def get_apps(self) -> list[AppConfig]:
        raw = self._client.get_apps_list(self._config.site_name)
        return fc_apps_list_to_appconfig_list(raw)

    def get_python_version(self) -> Optional[str]:
        deps = self._client.get_dependencies(self._config.site_name)
        for dep in deps:
            if dep.get("dependency", "").lower() == "python":
                return dep.get("version")
        return None

    def download_db_backup(self, dest_dir: Path) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        urls = self._client.get_latest_backup_download_urls(self._config.site_name, files=["database"])
        db_url = urls.get("database")
        if not db_url:
            raise RuntimeError(f"No database backup URL found for site {self._config.site_name}")

        if _requests is None:
            raise RuntimeError("requests library is required for downloading FC backups")

        file_name = db_url.split("?")[0].split("/")[-1]
        dest_path = dest_dir / file_name

        response = _requests.get(db_url, stream=True)
        response.raise_for_status()

        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        return dest_path
