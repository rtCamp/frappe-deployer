import json
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from fmd.config.config import Config
from fmd.config.app import AppConfig
from fmd.consts import DATA_DIR_NAME, BACKUP_DIR_NAME, RELEASE_DIR_NAME
from fmd.exceptions import SiteAlreadyConfigured, SiteNotConfigured
from fmd.helpers import get_relative_path, gen_name_with_timestamp
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
        self.bench_name = config.bench_name
        self.bench_path = config.bench_path
        self.workspace_root = config.workspace_root

        self.workspace_path = self.workspace_root / "workspace"
        self.current = BenchDirectory(config.bench_path)
        self.data = BenchDirectory(self.workspace_path / DATA_DIR_NAME)
        self.backup = BenchDirectory(self.workspace_root / BACKUP_DIR_NAME / gen_name_with_timestamp(RELEASE_DIR_NAME))
        self.new = BenchDirectory(self.workspace_path / gen_name_with_timestamp(RELEASE_DIR_NAME))

        self.app_service = AppService(exec_runner, host_runner, config, printer)
        self.backup_service = BackupService(exec_runner, host_runner, config, printer)
        self.bench_service = BenchService(exec_runner, host_runner, config, printer)
        self.image_bench_service = BenchService(image_runner, host_runner, config, printer)
        self.cleanup_service = CleanupService(exec_runner, host_runner, config, printer)
        self.symlink_service = SymlinkService(exec_runner, host_runner, config, printer)

        self.bench_cli: str = "bench"
        self.site_installed_apps: dict = {}

    def _get_merged_apps_list(self):
        apps = list(self.config.apps)

        if self.config.fc and self.config.release.use_fc_apps:
            try:
                from fmd.fc.data_source import FCDataSource

                fc_source = FCDataSource(self.config.fc)
                fc_apps = fc_source.get_apps()

                if fc_apps:
                    apps_by_repo = {app.repo.lower(): app for app in apps}

                    for fc_app in fc_apps:
                        repo_key = fc_app.repo.lower()
                        if repo_key in apps_by_repo:
                            local_app = apps_by_repo[repo_key]
                            local_app.ref = fc_app.ref
                        else:
                            apps.append(fc_app)

                    self.printer.print(f"Merged {len(fc_apps)} apps from Frappe Cloud")
            except Exception as e:
                self.printer.warning(f"Failed to fetch FC apps: {e}")

        if self.config.fc and self.config.release.use_fc_deps:
            try:
                from fmd.fc.data_source import FCDataSource

                fc_source = FCDataSource(self.config.fc)
                fc_python_version = fc_source.get_python_version()

                if fc_python_version and not self.config.release.python_version:
                    self.config.release.python_version = fc_python_version
                    self.printer.print(f"Using Python {fc_python_version} from Frappe Cloud")
            except Exception as e:
                self.printer.warning(f"Failed to fetch FC python version: {e}")

        return apps

    def _create_temp_common_site_config(self, bench_directory: BenchDirectory) -> None:
        try:
            from frappe_manager.utils.helpers import get_bench_connection_config

            bench_name = self.bench_name or self.site_name
            merged_config = get_bench_connection_config(bench_name, "mariadb", 3306)

            merged_config.update({"socketio_port": 80, "webserver_port": 80})

            existing_config_path = self.data.common_site_config
            if existing_config_path.exists():
                with open(existing_config_path, "r") as f:
                    deployment_config = json.load(f)
                merged_config.update(deployment_config)
                self.printer.print("Merged deployment_data/common_site_config.json")

            if self.config.release.common_site_config:
                merged_config.update(self.config.release.common_site_config)

            config_path = bench_directory.sites / "common_site_config.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w") as f:
                json.dump(merged_config, f, indent=2)

            self.printer.print(f"Created temporary common_site_config.json")
        except Exception as e:
            self.printer.warning(f"Failed to create temporary common_site_config.json: {e}")

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
        d = self.config.switch
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

    def configure(self) -> None:
        backups = self.config.configure.backups

        if self.current.path.is_symlink():
            raise SiteAlreadyConfigured(str(self.current.path))

        renamed = False
        try:
            if backups:
                self.printer.change_head("Creating backup")
                self.backup_service.bench_db_and_configs_backup(
                    self.current, self.backup, self.site_name, self.bench_cli, self.workspace_root
                )
                self.printer.print("Backup completed")
            else:
                self.printer.print("Taking backup is disabled.")

            self.symlink_service.configure_data_dir(self.data, self.current, self.workspace_root)

            self.printer.change_head("Moving bench directory, creating initial release")
            self.current.path.rename(self.new.path)
            renamed = True
            new_bench = self.new

            self.symlink_service.configure_symlinks(self.data, new_bench)

            has_apps = new_bench.apps.exists() and any(d for d in new_bench.apps.iterdir() if d.is_dir())
            if has_apps:
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
            if self.config.configure.rollback:
                self._rollback_configure(renamed)
            raise

    def _seed_release_runtimes(self, release_path: Path) -> None:
        current_bench = self.bench_path.resolve() if self.bench_path.is_symlink() else self.bench_path
        release_uv = release_path / ".uv"
        release_fnm = release_path / ".fnm"

        src_uv = current_bench / ".uv"
        src_fnm = current_bench / ".fnm"

        if src_uv.is_dir() and not release_uv.exists():
            shutil.copytree(src_uv, release_uv, symlinks=True)
            self._open_permissions(release_uv)

        if src_fnm.is_dir() and not release_fnm.exists():
            shutil.copytree(src_fnm, release_fnm, symlinks=True)
            self._open_permissions(release_fnm)

    @staticmethod
    def _open_permissions(path: Path) -> None:
        for p in [path, *path.rglob("*")]:
            try:
                if not p.is_symlink():
                    p.chmod(0o777)
            except OSError:
                pass

    def _setup_supervisor_config(self, release_path: Path) -> None:
        try:
            _bs_mod = __import__(
                "frappe_manager.site_manager.modules.bench_supervisor",
                fromlist=["BenchSupervisor"],
            )
            BenchSupervisor = _bs_mod.BenchSupervisor
            _cl_mod = __import__("frappe_manager.logger.contextual", fromlist=["ContextualLogger"])
            ContextualLogger = _cl_mod.ContextualLogger
            _ctx_mod = __import__("frappe_manager.logger.context", fromlist=["LoggerContext"])
            LoggerContext = _ctx_mod.LoggerContext
        except Exception as e:
            self.printer.warning(f"Could not import FM BenchSupervisor, skipping supervisor config: {e}")
            return

        import logging

        _logger = ContextualLogger(logging.getLogger("fmd"), LoggerContext())
        supervisor = BenchSupervisor(logger=_logger, docker_client=None, config=None, bench_name=self.bench_name)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "workspace").mkdir()
            (tmp_path / "workspace" / "frappe-bench").symlink_to(release_path)
            try:
                supervisor.setup_supervisor(tmp_path, force=True)
            except Exception as e:
                self.printer.warning(f"Failed to generate supervisor config: {e}")

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

        env_bak = restore.path / "env.bak"
        env_dir = restore.path / "env"
        if env_bak.exists():
            if env_dir.exists() or env_dir.is_symlink():
                shutil.rmtree(env_dir) if env_dir.is_dir() else env_dir.unlink()
            shutil.move(str(env_bak), str(env_dir))

        if renamed and self.new.path.exists() and not self.current.path.exists():
            self.new.path.rename(self.current.path)

    def create(self, build_dir: Optional[Path] = None) -> str:
        if not self.config.ship and not self.bench_path.is_symlink():
            raise SiteNotConfigured(str(self.bench_path))

        self.printer.change_head("Configuring new release dirs")

        apps = self._get_merged_apps_list()

        if self.config.switch.backups and not self.config.ship:
            self.backup_service.bench_db_and_configs_backup(
                self.current, self.backup, self.site_name, self.bench_cli, self.workspace_root
            )

        base_dir = build_dir.resolve() if build_dir is not None else self.workspace_path
        self.new = BenchDirectory(base_dir / gen_name_with_timestamp(RELEASE_DIR_NAME))

        for dir_path in [self.new.path, self.new.apps, self.new.sites]:
            dir_path.mkdir(parents=True, exist_ok=True)
            self.printer.print(f"Created dir [blue]{dir_path.name}[/blue]")
        (self.new.path / "config" / "pids").mkdir(parents=True, exist_ok=True)
        (self.new.path / "logs").mkdir(parents=True, exist_ok=True)

        self._seed_release_runtimes(self.new.path)

        self.config.to_toml(self.new.path / ".fmd.toml")

        self.app_service.clone_apps(self.data, self.new, apps, self.site_name, self._is_app_installed)

        self._create_temp_common_site_config(self.new)
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

        return self.new.path.name

    def switch(self, release_name: str) -> None:
        release_path = self.workspace_path / release_name
        if not release_path.exists():
            raise RuntimeError(f"Release '{release_name}' not found at {release_path}")

        new = BenchDirectory(release_path)
        previous_release = self.bench_path.resolve()

        restore_db_file_path: Optional[Path] = None

        if self.config.switch.backups:
            self.backup_service.bench_db_and_configs_backup(
                self.current, self.backup, self.site_name, self.bench_cli, self.workspace_root
            )

        if self.config.fc and self.config.switch.use_fc_db:
            from fmd.fc.data_source import FCDataSource

            fc_source = FCDataSource(self.config.fc)
            restore_db_file_path = fc_source.download_db_backup(self.workspace_root / "deployment-backup" / "fc-db")

        self.backup_service.sync_configs_with_files(self.current, self.site_name)
        self.symlink_service.configure_symlinks(self.data, new)
        self.bench_service.bench_symlink(self.bench_path, new)
        self._seed_release_runtimes(new.path)

        try:
            if restore_db_file_path:
                self.backup_service.bench_restore(self.site_name, self.workspace_root, restore_db_file_path)
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
            self.bench_service.bench_clear_cache(self.current, self.bench_cli, self.site_name)
            self.site_installed_apps = self._get_site_installed_apps(self.current)
            self.app_service.bench_install_apps(
                self.current, self.config.apps, self.site_name, self.bench_cli, self._is_app_installed
            )
            self.cleanup_service.cleanup_releases(self.workspace_root, self.bench_path)

        except Exception as e:
            if self.config.switch.rollback:
                self.printer.warning(f"Failed to switch to release {release_name}, rolling back")
                if self.bench_path.exists() or self.bench_path.is_symlink():
                    self.bench_path.unlink()
                self.bench_service.bench_symlink(self.bench_path, BenchDirectory(previous_release))
                self.bench_service.bench_restart(
                    BenchDirectory(previous_release),
                    self.bench_path,
                    self.current,
                    self.site_name,
                    self._host_run,
                    **{**self._restart_kwargs(), "migrate": False},
                )
                self.printer.print("Rolled back to previous release")
            raise

    def _extract_python_version(self, release_path: Path) -> str:
        uv_default = release_path / ".uv" / "python-default"
        if not uv_default.is_symlink():
            return "N/A"
        try:
            target = uv_default.readlink()
            parts = str(target).split("/")
            for part in parts:
                if part.startswith("cpython-") or part.startswith("python-"):
                    version_part = part.replace("cpython-", "").replace("python-", "")
                    version = version_part.split("-")[0]
                    return version
        except Exception:
            pass
        return "N/A"

    def _extract_node_version(self, release_path: Path) -> str:
        fnm_default = release_path / ".fnm" / "aliases" / "default"
        if fnm_default.is_symlink():
            try:
                target = fnm_default.readlink()
                parts = str(target).split("/")
                for part in parts:
                    if part.startswith("v") and part[1:].replace(".", "").isdigit():
                        return part[1:]
            except Exception:
                pass

        node_versions = release_path / ".fnm" / "node-versions"
        if node_versions.exists():
            try:
                versions = [d.name for d in node_versions.iterdir() if d.is_dir() and d.name.startswith("v")]
                if versions:
                    return versions[0][1:]
            except Exception:
                pass

        return "N/A"

    def _collect_release_metadata(self, release_dir: Path, current_release: Optional[Path]) -> dict:
        apps_dir = release_dir / "apps"
        app_count = 0
        broken_symlinks = []

        if apps_dir.exists():
            for item in apps_dir.iterdir():
                if item.name in [".DS_Store", "__pycache__"]:
                    continue
                app_count += 1
                if item.is_symlink():
                    if not item.exists():
                        broken_symlinks.append(item.name)

        size = self.cleanup_service.get_dir_size(release_dir)
        python_version = self._extract_python_version(release_dir)
        node_version = self._extract_node_version(release_dir)

        return {
            "name": release_dir.name,
            "path": str(release_dir),
            "current": current_release is not None and release_dir.resolve() == current_release,
            "size": size,
            "python_version": python_version,
            "node_version": node_version,
            "app_count": app_count,
            "broken_symlinks": broken_symlinks,
        }

    def list_releases(self, callback=None) -> list[dict]:
        current_release = self.bench_path.resolve() if self.bench_path.is_symlink() else None
        workspace = self.workspace_path
        if not workspace.exists():
            return []
        release_dirs = sorted(
            [d for d in workspace.iterdir() if d.is_dir() and d.name.startswith(RELEASE_DIR_NAME)],
            key=lambda d: d.name,
            reverse=True,
        )

        from concurrent.futures import ThreadPoolExecutor, as_completed
        import os

        max_workers = min(len(release_dirs), os.cpu_count() or 4)
        releases_list: list[dict] = []
        results_map = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(self._collect_release_metadata, d, current_release): i
                for i, d in enumerate(release_dirs)
            }

            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    result = future.result()
                    results_map[index] = result
                    if callback:
                        callback(result, index)
                except Exception as e:
                    error_result = {
                        "name": release_dirs[index].name,
                        "path": str(release_dirs[index]),
                        "current": False,
                        "size": "Error",
                        "python_version": "N/A",
                        "node_version": "N/A",
                        "app_count": 0,
                        "broken_symlinks": [],
                        "error": str(e),
                    }
                    results_map[index] = error_result
                    if callback:
                        callback(error_result, index)

        for i in range(len(release_dirs)):
            releases_list.append(results_map[i])

        return releases_list

    def _restart_kwargs(self) -> dict:
        d = self.config.switch
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
