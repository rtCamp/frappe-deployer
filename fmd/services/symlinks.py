import shutil
from pathlib import Path
from typing import Any

from fmd.release_directory import BenchDirectory
from fmd.helpers import get_relative_path
from fmd.consts import DATA_DIR_NAME


def _replace_with_symlink(path: Path, target: Path, target_is_directory: bool):
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()
    path.symlink_to(target, target_is_directory)


class SymlinkService:
    def __init__(self, runner: Any, host_runner: Any, config: Any, printer: Any):
        self.runner = runner
        self.host_runner = host_runner
        self.config = config
        self.printer = printer

    def configure_symlinks(self, data: BenchDirectory, new: BenchDirectory):
        self.printer.change_head("Configuring symlinks")

        self.sync_sites_to_data_dir(data, new)

        if not data.common_site_config.exists():
            raise RuntimeError(f"{data.common_site_config.absolute()} doesn't exist. Please Check")

        _replace_with_symlink(
            new.common_site_config, get_relative_path(new.common_site_config, data.common_site_config), False
        )
        self.printer.print(f"Symlink [blue]{new.common_site_config.name}[/blue] ")

        if data.config.exists():
            _replace_with_symlink(new.config, get_relative_path(new.config, data.config), True)
            self.printer.print(f"Symlink [blue]{new.config.name}[/blue] ")

        if data.logs.exists():
            _replace_with_symlink(new.logs, get_relative_path(new.logs, data.logs), True)
            self.printer.print(f"Symlink [blue]{new.logs.name}[/blue] ")

    def sync_sites_to_data_dir(self, data: BenchDirectory, new: BenchDirectory):
        self.printer.change_head("Syncing sites to data directory")

        data.sites.mkdir(parents=True, exist_ok=True)

        for site in data.list_sites():
            data_site_path = data.sites / site.name
            new_site_path = new.sites / site.name
            new_site_path.mkdir(parents=True, exist_ok=True)

            if new_site_path.exists():
                for item in new_site_path.iterdir():
                    data_item_path = data_site_path / item.name
                    if not data_item_path.exists():
                        shutil.move(str(item), str(data_item_path))
                        self.printer.print(f"Moved new item {item.name} to data directory")

            for item in data_site_path.iterdir():
                data_item_path = data_site_path / item.name
                site_item_symlink = new_site_path / item.name
                if not site_item_symlink.exists():
                    relative_path = get_relative_path(site_item_symlink, data_item_path)
                    site_item_symlink.symlink_to(relative_path, True)
                    self.printer.print(f"Symlink {site_item_symlink.name} --> {relative_path}")

    def configure_data_dir(self, data: BenchDirectory, current: BenchDirectory, deploy_dir_path: Path):
        if not data.path.exists():
            self.printer.change_head(f"Creating {DATA_DIR_NAME} dir")
            data.path.mkdir()
            self.printer.print("Created release data dir")

        self.printer.change_head("Moving sites into data dir")
        data.sites.mkdir(parents=True, exist_ok=True)
        for site in current.list_sites():
            data_site_path = data.sites / site.name
            shutil.move(str(site.absolute()), str(data_site_path.absolute()))
            self.printer.print(f"Moved {site.name}")

        if current.common_site_config.exists():
            self.printer.change_head("Moving common_site_config.json into data dir")
            shutil.move(str(current.common_site_config.absolute()), str(data.common_site_config.absolute()))
            self.printer.print("Moved common_site_config.json and created symlink")

        if current.logs.exists():
            self.printer.change_head("Moving logs into data dir")
            shutil.move(str(current.logs.absolute()), str(data.logs.absolute()))
            self.printer.print("Moved logs and created symlink")

        if current.config.exists():
            self.printer.change_head("Moving config into data dir")
            shutil.move(str(current.config.absolute()), str(data.config.absolute()))
            self.printer.print("Moved config")
