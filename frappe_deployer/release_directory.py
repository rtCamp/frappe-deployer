from dataclasses import dataclass
import re
from pathlib import Path
import shutil

from frappe_deployer.helpers import gen_name_with_timestamp, get_relative_path

RELEASE_BASE_NAME = 'release'

@dataclass
class BenchDirectory:
    path: Path

    @property
    def is_configured(self) -> bool:
        return self.path.is_symlink()

    @property
    def logs(self) -> Path:
        return self.path / 'logs'

    @property
    def config(self) -> Path:
        return self.path / 'sites'

    @property
    def apps(self) -> Path:
        return self.path / 'apps'

    @property
    def sites(self) -> Path:
        return self.path / 'sites'

    @property
    def common_site_config(self) -> Path:
        return self.sites / 'common_site_config.json'

    @property
    def nginx_conf(self) -> Path:
        return self.config / 'nginx.conf'

    def list_sites(self) -> list[Path]:
        """Returns a list of site names (directories) within the sites directory that are FQDNs."""
        if self.sites.exists() and self.sites.is_dir():
            return [
                site for site in self.sites.iterdir()
                if site.is_dir() and self.is_fqdn(site.name)
            ]
        return []

    @staticmethod
    def is_fqdn(name: str) -> bool:
        """Validates if the given name is a fully qualified domain name (FQDN)."""
        # Simple FQDN validation: contains at least one dot and does not start or end with a dot
        return bool(re.match(r'^(?!-)[A-Za-z0-9-]{1,63}(?<!-)\.(?!-)[A-Za-z0-9-]{1,63}(?<!-)$', name))
