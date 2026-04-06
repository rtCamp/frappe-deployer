import json
import shutil
from pathlib import Path
from typing import Optional

from fmd.config.config import Config
from fmd.config.app import AppConfig
from fmd.consts import DATA_DIR_NAME, BACKUP_DIR_NAME, RELEASE_SUFFIX, RELEASE_DIR_NAME
from fmd.exceptions import SiteAlreadyConfigured, SiteNotConfigured
from fmd.helpers import get_relative_path
from fmd.release_directory import BenchDirectory
from fmd.services.apps import AppService
from fmd.services.backup import BackupService
from fmd.services.bench import BenchService
from fmd.services.cleanup import CleanupService
from fmd.services.symlinks import SymlinkService


class ReleaseManager:
    def __init__(self, config: Config, image_runner, exec_runner, host_runner, printer):
        self.config = config
        self.image_runner = image_runner
        self.exec_runner = exec_runner
        self.host_runner = host_runner
        self.printer = printer

        self.site_name = config.site_name
        self.bench_path = config.bench_path
        self.deploy_dir_path = config.deploy_dir_path

        self.workspace_path = self.deploy_dir_path / "workspace"
        self.current = BenchDirectory(config.bench_path)
        self.data = BenchDirectory(self.workspace_path / DATA_DIR_NAME)
        self.backup = BenchDirectory(self.deploy_dir_path / BACKUP_DIR_NAME / RELEASE_SUFFIX)
        self.new = BenchDirectory(self.workspace_path / RELEASE_SUFFIX)

        self.app_service = AppService(exec_runner, host_runner, config, printer)
        self.backup_service = BackupService(exec_runner, host_runner, config, printer)
        self.bench_service = BenchService(exec_runner, host_runner, config, printer)
        self.image_bench_service = BenchService(image_runner, host_runner, config, printer)
        self.cleanup_service = CleanupService(exec_runner, host_runner, config, printer)
        self.symlink_service = SymlinkService(exec_runner, host_runner, config, printer)

        self.bench_cli: str = "bench"
        self.site_installed_apps: dict = {}

    def _get_site_installed_apps(self, bench_directory: BenchDirectory) -> dict:
        command = [self.bench_cli, "list-apps", "-f", "json"]
        try:
            output = self.exec_runner.run(
                command,
                bench_directory,
                capture_output=True,
                workdir=self.exec_runner.workdir_for_bench(bench_directory),
            )
            if getattr(output, "combined", None):
                return json.loads("".join(output.stdout))
        except Exception:
            self.printer.warning(f"Not able to get current list of apps installed in {self.site_name}")
        return {self.site_name: []}

    def _is_app_installed(self, site_name: str, app_name: str) -> bool:
        site_apps = self.site_installed_apps.get(site_name, [])
        return app_name in site_apps

    def _host_run(
        self, command, bench_directory, container=False, capture_output=True, workdir=None, env=None, **kwargs
    ):
        runner = self.exec_runner if container else self.host_runner
        return runner.run(command, bench_directory, capture_output=capture_output, workdir=workdir, env=env)

    def _bench_restart_args(self) -> list[str]:
        args = []
        d = self.config.deploy
        if d.migrate:
            args += ["--migrate"]
            if d.migrate_timeout:
                args += ["--migrate-timeout", str(d.migrate_timeout)]
            if d.migrate_command:
                args += ["--migrate-command", d.migrate_command]
        if d.drain_workers:
            args += ["--drain-workers"]
            if d.drain_workers_timeout:
                args += ["--drain-workers-timeout", str(d.drain_workers_timeout)]
            if d.drain_workers_poll:
                args += ["--drain-workers-poll", str(d.drain_workers_poll)]
            if d.skip_stale_workers:
                args += ["--skip-stale-workers"]
            else:
                args += ["--no-skip-stale-workers"]
            if d.skip_stale_timeout:
                args += ["--skip-stale-timeout", str(d.skip_stale_timeout)]
            if d.worker_kill_timeout:
                args += ["--worker-kill-timeout", str(d.worker_kill_timeout)]
            if d.worker_kill_poll:
                args += ["--worker-kill-poll", str(d.worker_kill_poll)]
        if d.maintenance_mode and d.maintenance_mode_phases:
            for phase in d.maintenance_mode_phases:
                args += ["--maintenance-mode", phase]
        return args

    def _search_and_replace_in_database(self, search: str, replace: str, dry_run: bool = False) -> None:
        search_replace_script = Path(__file__).parent.parent / "search_replace.py"
        if not search_replace_script.exists():
            self.printer.warning(f"Search/replace script not found at {search_replace_script}")
            return

        bench_script_path = self.current.sites / "search_replace.py"
        shutil.copy2(search_replace_script, bench_script_path)

        try:
            python_path = "../env/bin/python"
            cmd = [python_path, "search_replace.py", self.site_name, search, replace]
            if dry_run:
                cmd.append("--dry-run")
            if self.config.verbose:
                cmd.append("--verbose")

            result = self.exec_runner.run(
                cmd,
                self.current,
                capture_output=True,
                workdir=self.exec_runner.workdir_for_sites(self.current),
            )
            if getattr(result, "combined", None):
                for line in result.combined:
                    if line.strip():
                        self.printer.print(line.strip())
        except Exception as e:
            self.printer.warning(f"Failed to perform search and replace: {str(e)}")
        finally:
            if bench_script_path.exists():
                bench_script_path.unlink()

    def configure(self, backups: Optional[bool] = None) -> None:
        if backups is None:
            backups = self.config.deploy.backups

        if self.current.path.is_symlink():
            raise SiteAlreadyConfigured(str(self.current.path))

        renamed = False
        try:
            if backups:
                self.printer.change_head("Creating backup")
                self.backup_service.bench_db_and_configs_backup(
                    self.current, self.backup, self.site_name, self.bench_cli, self.deploy_dir_path
                )
                self.printer.print("Backup completed")
            else:
                self.printer.print("Taking backup is disabled.")

            self.symlink_service.configure_data_dir(self.data, self.current, self.deploy_dir_path)

            self.printer.change_head("Moving bench directory, creating initial release")
            self.current.path.rename(self.new.path)
            renamed = True
            new_bench = self.new

            self.symlink_service.configure_symlinks(self.data, new_bench)

            self.image_bench_service.bench_setup_requirements(
                new_bench,
                self.config.apps,
                self.bench_cli,
                self.current,
                self.bench_path,
                self.site_name,
                self._host_run,
            )
            self.bench_service.bench_symlink(self.bench_path, new_bench)
            self.bench_service.bench_restart(
                new_bench,
                self.bench_path,
                self.current,
                self.site_name,
                self._host_run,
                **self._restart_kwargs(),
            )

        except Exception:
            self._rollback_configure(renamed)
            raise

    def _rollback_configure(self, renamed: bool) -> None:
        self.printer.print(f"Rollback\n{'--' * 10}")
        restore = self.new if renamed else self.current

        if self.bench_path.is_symlink():
            self.bench_path.unlink()

        for path in [restore.config, restore.logs, restore.common_site_config]:
            if path.is_symlink():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)

        if restore.sites.exists():
            for site_dir in list(restore.sites.iterdir()):
                if not site_dir.is_dir():
                    continue
                for item in list(site_dir.iterdir()):
                    if item.is_symlink():
                        item.unlink()
                try:
                    site_dir.rmdir()
                except OSError:
                    pass

        if self.data.config.exists() and not restore.config.exists():
            shutil.move(str(self.data.config), str(restore.config))

        if self.data.logs.exists() and not restore.logs.exists():
            shutil.move(str(self.data.logs), str(restore.logs))

        if self.data.sites.exists():
            for site_dir in list(self.data.sites.iterdir()):
                if site_dir.is_dir():
                    restore_site = restore.sites / site_dir.name
                    if restore_site.exists():
                        try:
                            restore_site.rmdir()
                        except OSError:
                            pass
                    shutil.move(str(site_dir), str(restore_site))
            if self.data.common_site_config.exists() and not restore.common_site_config.exists():
                shutil.move(str(self.data.common_site_config), str(restore.common_site_config))

        if self.data.path.exists():
            shutil.rmtree(self.data.path)

        if renamed and self.new.path.exists() and not self.current.path.exists():
            self.new.path.rename(self.current.path)

    def create(self) -> str:
        if not self.bench_path.is_symlink():
            raise SiteNotConfigured(str(self.bench_path))

        self.printer.change_head("Configuring new release dirs")
        self.site_installed_apps = self._get_site_installed_apps(self.current)

        apps = self.config.apps

        if self.config.deploy.backups:
            self.backup_service.bench_db_and_configs_backup(
                self.current, self.backup, self.site_name, self.bench_cli, self.deploy_dir_path
            )

        for dir_path in [self.new.path, self.new.apps, self.new.sites]:
            dir_path.mkdir(exist_ok=True)
            self.printer.print(f"Created dir [blue]{dir_path.name}[/blue]")
        (self.new.path / "config" / "pids").mkdir(parents=True, exist_ok=True)

        self.config.to_toml(self.new.path / f"{self.site_name}.toml")
        self.symlink_service.configure_symlinks(self.data, self.new)

        self.app_service.clone_apps(self.data, self.new, apps, self.site_name, self._is_app_installed)

        self.image_bench_service.bench_setup_requirements(
            self.new,
            apps,
            self.bench_cli,
            self.current,
            self.bench_path,
            self.site_name,
            self._host_run,
        )
        self.image_bench_service.bench_build(
            self.new,
            apps,
            self.bench_cli,
            self.current,
            self.bench_path,
            self.site_name,
            self._host_run,
        )
        if apps:
            self.image_bench_service.bench_clear_cache(self.new, self.bench_cli)

        return self.new.path.name

    def switch(self, release_name: str) -> None:
        release_path = self.workspace_path / release_name
        if not release_path.exists():
            raise RuntimeError(f"Release '{release_name}' not found at {release_path}")

        new = BenchDirectory(release_path)
        previous_release = self.bench_path.resolve()

        restore_db_file_path: Optional[Path] = None

        if self.config.deploy.backups:
            self.backup_service.bench_db_and_configs_backup(
                self.current, self.backup, self.site_name, self.bench_cli, self.deploy_dir_path
            )

        if self.config.fc and self.config.fc.use_db:
            from fmd.fc.data_source import FCDataSource

            fc_source = FCDataSource(self.config.fc)
            restore_db_file_path = fc_source.download_db_backup(self.deploy_dir_path / "deployment-backup" / "fc-db")

        self.backup_service.sync_configs_with_files(self.current, self.site_name)
        self.bench_service.bench_symlink(self.bench_path, new)

        try:
            if restore_db_file_path:
                self.backup_service.bench_restore(self.site_name, self.deploy_dir_path, restore_db_file_path)
                if restore_db_file_path.exists():
                    restore_db_file_path.unlink()

            self.bench_service.bench_restart(
                new,
                self.bench_path,
                self.current,
                self.site_name,
                self._host_run,
                **self._restart_kwargs(),
            )
            self.site_installed_apps = self._get_site_installed_apps(self.current)
            self.app_service.bench_install_apps(
                self.current, self.config.apps, self.site_name, self.bench_cli, self._is_app_installed
            )
            self.cleanup_service.cleanup_releases(self.deploy_dir_path, self.bench_path)

        except Exception as e:
            if self.config.deploy.rollback:
                self.printer.error(f"Failed to switch to release {release_name}, rolling back")
                if self.bench_path.exists() or self.bench_path.is_symlink():
                    self.bench_path.unlink()
                self.bench_service.bench_symlink(self.bench_path, BenchDirectory(previous_release))
                self.bench_service.bench_restart(
                    BenchDirectory(previous_release),
                    self.bench_path,
                    self.current,
                    self.site_name,
                    self._host_run,
                    **self._restart_kwargs(),
                )
                self.printer.print("Rolled back to previous release")
            raise

    def list_releases(self) -> list[dict]:
        current_release = self.bench_path.resolve() if self.bench_path.is_symlink() else None
        workspace = self.workspace_path
        if not workspace.exists():
            return []
        release_dirs = sorted(
            [d for d in workspace.iterdir() if d.is_dir() and d.name.startswith(RELEASE_DIR_NAME)],
            key=lambda d: d.name,
            reverse=True,
        )
        return [
            {
                "name": d.name,
                "path": str(d),
                "current": current_release is not None and d.resolve() == current_release,
            }
            for d in release_dirs
        ]

    def _restart_kwargs(self) -> dict:
        d = self.config.deploy
        return {
            "migrate": d.migrate,
            "migrate_timeout": getattr(d, "migrate_timeout", 300),
            "migrate_command": getattr(d, "migrate_command", None),
            "drain_workers": getattr(d, "drain_workers", False),
            "drain_workers_timeout": getattr(d, "drain_workers_timeout", 300),
            "drain_workers_poll": getattr(d, "drain_workers_poll", 5),
            "skip_stale_workers": getattr(d, "skip_stale_workers", True),
            "skip_stale_timeout": getattr(d, "skip_stale_timeout", 15),
            "worker_kill_timeout": getattr(d, "worker_kill_timeout", 15),
            "worker_kill_poll": getattr(d, "worker_kill_poll", 3.0),
            "maintenance_phases": d.maintenance_mode_phases if d.maintenance_mode else None,
        }
