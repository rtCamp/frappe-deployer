from pathlib import Path
from typing import Any, Optional
import gzip
import shutil
import importlib
import base64

from fmd.release_directory import BenchDirectory
from fmd.helpers import get_json, update_json_keys_in_file_path

_mm = None
try:
    _mm = importlib.import_module("frappe_manager.migration_manager.migration_helpers")
except Exception:
    _mm = None

MigrationBench = getattr(_mm, "MigrationBench", None)


def _create_migration_bench(name: str, path: Path):
    if MigrationBench is None:
        raise RuntimeError("FM migration support not available in this environment")
    return MigrationBench(name=name, path=path)


class BackupService:
    def __init__(self, runner: Any, host_runner: Any, config: Any, printer: Any):
        self.runner = runner
        self.host_runner = host_runner
        self.config = config
        self.printer = printer

    def bench_db_and_configs_backup(
        self,
        current: BenchDirectory,
        backup: BenchDirectory,
        site_name: str,
        bench_cli: str,
        workspace_root: Path,
    ):
        if self.config.switch.backups:
            self.printer.change_head("Backing up db, common_site_config and site_config.json")
            (backup.sites / site_name).mkdir(exist_ok=True, parents=True)
            shutil.copyfile(current.common_site_config, backup.common_site_config)
            frappe_app_dir = current.apps / "frappe"
            if frappe_app_dir.exists():
                self.bench_backup(current, backup, site_name, bench_cli, workspace_root)
                self.printer.print("Backed up db, common_site_config and site_config.json")
            else:
                self.printer.print("Skipped DB backup: apps/frappe does not exist in current bench.")

    def bench_backup(
        self,
        current: BenchDirectory,
        backup: BenchDirectory,
        site_name: str,
        bench_cli: str,
        workspace_root: Path,
        file_name: Optional[str] = None,
        using_bench_backup: bool = True,
        compress: bool = True,
        sql_delete_after_compress: bool = True,
    ) -> Optional[Path]:
        self.printer.change_head(f"Exporting {site_name} db")

        file_name = f"{site_name if file_name is None else file_name}.sql.gz"

        host_backup_db_path = backup.path / file_name

        backup_config_path = self.runner.backup_path(backup.path, "site_config.json")
        backup_db_path = self.runner.backup_path(backup.path, file_name)

        if using_bench_backup:
            db_export_command = [
                bench_cli,
                "backup",
                "--backup-path-conf",
                backup_config_path,
                "--backup-path-db",
                backup_db_path,
            ]

            self.runner.run(db_export_command, current, capture_output=True)

            return host_backup_db_path

        backup_bench = _create_migration_bench(name=site_name, path=workspace_root)
        backup_bench_db_info = backup_bench.get_db_connection_info()

        bench_db_name = backup_bench_db_info.get("name")
        mariadb_client = self._get_mariadb_client(site_name, workspace_root)

        # db_export runs mysqldump inside `site_name`'s frappe container, where the
        # bench workspace is mounted at /workspace. Write the dump under that mount so
        # the --result-file path exists in the container and is readable on the host.
        # (backup.path points at the target bench and is NOT mounted in this container,
        # which is why restoring from another site failed with "No such file or directory".)
        sql_file_name = file_name[: -len(".gz")] if file_name.endswith(".gz") else file_name
        container_db_path = f"/workspace/{sql_file_name}"
        host_backup_db_path = workspace_root / "workspace" / sql_file_name

        mariadb_client.db_export(bench_db_name, export_file_path=container_db_path)

        self.printer.print(f"Exported {site_name} db")

        if compress:
            self.printer.change_head(f"Compress {site_name} db")
            with open(host_backup_db_path, "rb") as f_in:
                with gzip.open(str(host_backup_db_path) + ".gz", "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

            if sql_delete_after_compress:
                if host_backup_db_path.exists():
                    host_backup_db_path.unlink()

            self.printer.print("DB has been compressed.")

        return host_backup_db_path

    def bench_restore(self, site_name: str, workspace_root: Path, db_file_path: Path):
        if not self.runner.supports_db_restore:
            self.printer.warning("db restore is not implemented in host mode")
            return

        if db_file_path.suffix == ".gz":
            self.printer.change_head(f"Decompressing {db_file_path}")
            with gzip.open(db_file_path, "rb") as f_in:
                decompressed_path = db_file_path.with_suffix("")
                with open(decompressed_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            db_file_path = decompressed_path

        backup_bench = _create_migration_bench(name=site_name, path=workspace_root)

        self.printer.change_head(f"Restoring {site_name} with db from {db_file_path}")

        backup_bench_db_info = backup_bench.get_db_connection_info()

        bench_db_name = backup_bench_db_info.get("name")

        mariadb_client = self._get_mariadb_client(site_name, workspace_root)

        mariadb_client.db_import(db_name=bench_db_name, host_db_file_path=db_file_path)
        self.printer.print(f"Restored {site_name} with db from {db_file_path}")

    def _get_mariadb_client(self, site_name: str, workspace_root: Path) -> Any:
        from frappe_manager.services_manager.database_service_manager import (
            DatabaseServerServiceInfo,
            MariaDBManager,
        )

        bench = _create_migration_bench(name=site_name, path=workspace_root)
        db_info = DatabaseServerServiceInfo.import_from_bench(bench.name, bench.path)
        return MariaDBManager(
            db_info,
            bench.compose_file_manager,
            bench.docker,
            run_on_compose_service="frappe",
        )

    def run_frappe_python(self, site_name: str, workspace_root: Path, python_code: str) -> Any:
        """Run Python inside the bench's Frappe context via frappe-manager's docker API.

        Mirrors `fm shell --bench-console`: wrap the code with frappe.init/connect,
        base64-encode it, and pipe it into the bench venv interpreter inside the running
        `frappe` service. Nothing is written into the bench, and the interpreter is
        invoked by its own absolute path (so no sys.prefix RuntimeWarning).
        """
        bench = _create_migration_bench(name=site_name, path=workspace_root)

        wrapper = (
            "import sys, os\n"
            "os.chdir('/workspace/frappe-bench/sites')\n"
            "sys.path.insert(0, '/workspace/frappe-bench/apps')\n"
            "import frappe\n"
            f"frappe.init(site={site_name!r})\n"
            "frappe.connect()\n"
            f"{python_code}\n"
        )
        encoded = base64.b64encode(wrapper.encode()).decode()
        command = f"FM_EXEC_CODE='{encoded}' && echo $FM_EXEC_CODE | base64 -d | /workspace/frappe-bench/env/bin/python"

        return bench.docker.compose.exec(
            service="frappe",
            command=f'/bin/bash -c "{command}"',
            user="frappe",
            workdir="/workspace/frappe-bench",
            stream=False,
            capture_output=True,
            use_shlex_split=True,
        )

    def sync_db_encryption_key_from_site(
        self, current: BenchDirectory, from_bench_name: str, from_site_name: str, site_name: str, benches_dir: Path
    ):
        self.printer.change_head(f"Copying db_encryption_key from {from_bench_name}")

        site_config_path = (
            benches_dir / from_bench_name / "workspace" / "frappe-bench" / "sites" / from_site_name / "site_config.json"
        )
        site_config_data = get_json(site_config_path)
        encryption_key = site_config_data.get("encryption_key", None)

        if encryption_key:
            current_site_config_path = current.sites / site_name / "site_config.json"
            update_json_keys_in_file_path(current_site_config_path, {"encryption_key": encryption_key})
            self.printer.print(f"Copied encryption_key from {from_bench_name}")

    def sync_configs_with_files(self, current: BenchDirectory, site_name: str):
        self.printer.change_head("Updating common_site_config.json, site_config.json")
        common_site_config_path = current.sites / "common_site_config.json"

        site_config_path = current.sites / site_name / "site_config.json"

        if self.config.switch.common_site_config:
            update_json_keys_in_file_path(common_site_config_path, self.config.switch.common_site_config)

        if self.config.switch.site_config:
            update_json_keys_in_file_path(
                site_config_path,
                self.config.switch.site_config,
                merge_data=True if self.config.fc else False,
            )

        self.printer.print("Updated common_site_config.json, site_config.json")
