from pathlib import Path
import shutil
import time
import gzip
from typing import Iterable, Literal, Optional, Tuple, Union

from frappe_manager import CLI_DIR
from frappe_manager.compose_manager.ComposeFile import ComposeFile
from frappe_manager.compose_project.compose_project import ComposeProject
from frappe_manager.logger.log import richprint
from frappe_manager.migration_manager.migration_helpers import (
    MigrationBench,
    MigrationServicesManager,
)
from frappe_manager.services_manager.database_service_manager import (
    DatabaseServerServiceInfo,
    MariaDBManager,
)
from frappe_manager.utils.docker import (
    DockerException,
    SubprocessOutput,
    run_command_with_exit_code,
)
from frappe_manager.utils.helpers import json
from rich.rule import Rule
from frappe_deployer.config.app import AppConfig
from frappe_deployer.config.config import Config
from frappe_deployer.consts import (
    BACKUP_DIR_NAME,
    DATA_DIR_NAME,
    RELEASE_DIR_NAME,
    RELEASE_SUFFIX,
)
from frappe_deployer.exceptions import SiteAlreadyConfigured
from frappe_deployer.helpers import (
    get_json,
    get_relative_path,
    human_readable_time,
    update_json_keys_in_file_path,
)
from frappe_deployer.release_directory import BenchDirectory

class DeploymentManager:
    apps: list[AppConfig]
    path: Path
    verbose: bool = False
    mode: Literal["fm", "host"] = "fm"

    def __init__(self, config: Config) -> None:
        self.config = config
        self.verbose = config.verbose
        self.site_name = config.site_name
        self.bench_path = config.bench_path

        self.apps = config.apps
        self.mode = config.mode
        self.path = config.deploy_dir_path
        self.printer = richprint
        self.bench_cli = "bench"

        self.current = BenchDirectory(config.bench_path)
        self.site_installed_apps = self.get_site_installed_apps(self.current)

        self.data = BenchDirectory(self.path / DATA_DIR_NAME)
        self.backup = BenchDirectory(self.path / BACKUP_DIR_NAME / RELEASE_SUFFIX)
        self.new = BenchDirectory(self.path / RELEASE_SUFFIX)

        self.previous_release_dir = self.current.path.resolve()

        self.printer.start("Working")
        self.configure_bench_cli()

    def configure_bench_cli(self):
        # Step 1: Create a virtual environment in ~/.cache/frappe-deployer-venv
        venv_path = Path.home() / ".cache" / "frappe-deployer-venv"

        if self.mode == 'fm':
            venv_path =  Path("/workspace/.cache/frappe-deployer-venv")

        # Check if the virtual environment exists
        if not venv_path.exists() or not (venv_path / "bin" / "bench").exists():
            self.python_env_create(self.current, venv_path=str(venv_path))

            # Step 2: Install bench and frappe from given GitHub tags link using uv
            bench_install_command = [
                "uv", "pip",
                "install",
                "--python",
                f"{str(venv_path)}/bin/python",
                "git+https://github.com/frappe/bench.git",
                "git+https://github.com/frappe/frappe.git"
            ]

            self.host_run(
                bench_install_command,
                self.current,
                container=self.mode == "fm",
                capture_output=False
            )

        # Step 3: Use this bench from this venv in subsequent runs
        self.bench_cli = str((venv_path / "bin" / "bench").absolute())

    def sync_sites_to_data_dir(self):
        """Sync sites from current bench to data directory"""
        self.printer.change_head("Syncing sites to data directory")

        # Create data sites directory if it doesn't exist
        self.data.sites.mkdir(parents=True, exist_ok=True)

        # Move all sites from current bench to data directory
        # for site in self.current.list_sites():
        #     data_site_path = self.data.sites / site.name

        #     # Skip if site already exists in data directory
        #     if data_site_path.exists():
        #         self.printer.print(f"Site {site.name} already exists in data directory")
        #         continue

        #     # Move site to data directory
        #     shutil.move(str(site.absolute()), str(data_site_path.absolute()))
        #     self.printer.print(f"Moved {site.name} to data directory")

        # Create symlinks from new bench to data directory and handle new files
        for site in self.data.list_sites():
            data_site_path = self.data.sites / site.name
            new_site_path = self.new.sites / site.name
            new_site_path.mkdir(parents=True, exist_ok=True)

            # First, check for new files/dirs in new_site_path that don't exist in data_site_path
            if new_site_path.exists():
                for item in new_site_path.iterdir():
                    data_item_path = data_site_path / item.name
                    if not data_item_path.exists():
                        # Move new item to data directory
                        shutil.move(str(item), str(data_item_path))
                        self.printer.print(f"Moved new item {item.name} to data directory")

            # Create symlinks for all files in data site directory
            for item in data_site_path.iterdir():
                data_item_path = data_site_path / item.name
                site_item_symlink = new_site_path / item.name
                if not site_item_symlink.exists():
                    relative_path = get_relative_path(site_item_symlink, data_item_path)
                    site_item_symlink.symlink_to(relative_path, True)
                    self.printer.print(f"Symlink {site_item_symlink.name} --> {relative_path}")

    def configure_symlinks(self):
        self.printer.change_head("Configuring symlinks")

        # Sync sites to data directory
        self.sync_sites_to_data_dir()

        # common_site_config.json
        if not self.data.common_site_config.exists():
            raise RuntimeError(
                f"{self.data.common_site_config.absolute()} doesn't exist. Please Check"
            )

        self.new.common_site_config.symlink_to(
            get_relative_path(
                self.new.common_site_config, self.data.common_site_config
            ),
            True,
        )
        self.printer.print(f"Symlink [blue]{self.new.common_site_config.name}[/blue] ")

        # config
        if not self.data.config.exists():
            raise RuntimeError(
                f"{self.data.config.absolute()} doesn't exist. Please Check"
            )

        self.new.config.symlink_to(
            get_relative_path(self.new.config, self.data.config), True
        )
        self.printer.print(f"Symlink [blue]{self.new.config.name}[/blue] ")

        # logs
        if not self.data.logs.exists():
            self.printer.print("logs directory doesn't exists recreating it")
            self.data.logs.mkdir(parents=True)

        self.new.logs.symlink_to(get_relative_path(self.new.logs, self.data.logs), True)
        self.printer.print(f"Symlink [blue]{self.new.logs.name}[/blue] ")

    def configure_data_dir(self):

        if not self.data.path.exists():
            self.printer.change_head(f"Creating {DATA_DIR_NAME} dir")
            self.data.path.mkdir()
            self.printer.print("Created release data dir")

        # move all sites
        self.printer.change_head("Moving sites into data dir")
        for site in self.current.list_sites():
            data_site_path = self.data.sites / site.name
            shutil.move(str(site.absolute()), str(data_site_path.absolute()))
            self.printer.print(f"Moved {site.name}")

        # common_site_config.json
        if self.current.common_site_config.exists():
            self.printer.change_head(
                "Moving common_site_config.json into data dir"
            )
            shutil.move(
                str(self.current.common_site_config.absolute()),
                str(self.data.common_site_config.absolute()),
            )
            self.printer.print(
                "Moved common_site_config.json and created symlink"
            )

        # logs
        if self.current.logs.exists():
            self.printer.change_head("Moving logs into data dir")
            shutil.move(
                str(self.current.logs.absolute()),
                str(self.data.logs.absolute()),
            )
            self.printer.print("Moved logs and created symlink")

        # config
        if self.current.config.exists():
            self.printer.change_head("Moving logs into data dir")
            shutil.move(
                str(self.current.config.absolute()),
                str(self.data.config.absolute()),
            )
            self.printer.print("Moved logs and created symlink")


    @staticmethod
    def configure(config: Config, only_move: bool = False, backups: Optional[bool]=None):
        if not backups:
            backups = config.backups

        release = DeploymentManager(config)

        if release.current.path.is_symlink():
            raise SiteAlreadyConfigured(str(release.current.path))

        try:
            if backups:
                release.printer.change_head("Creating backup")
                shutil.copytree(config.bench_path, release.backup.path / 'configure' , symlinks=True)
                release.bench_db_and_configs_backup()
                release.printer.print("Backup completed")
            else:
                release.printer.error('Taking backup is disabled.')

            release.configure_data_dir()

            if only_move:
                return

            release.configure_symlinks()

            # bench
            release.printer.change_head(
                f"Moving bench directory, creating initial release"
            )
            shutil.move(
                str(release.current.path.absolute()), str(release.new.path.absolute())
            )

            release.configure_uv(release.new)
            release.bench_setup_requiments(release.new)
            release.bench_symlink_and_restart(release.new)

            release.bench_build(release.new)
            release.bench_install_and_migrate(release.current)

        except Exception as e:
            if backups:
                release.printer.print(f'Rollback\n{"--"*10} ')
                release.printer.change_head(
                    f"Deleting the {release.current.path.name} tangled deployment"
                )
                if release.current.path.exists():
                    if release.current.path.is_symlink():
                        release.current.path.unlink()
                    else:
                        shutil.rmtree(release.current.path)

                release.printer.print(
                    f"Deleted the {release.current.path.name} tangled deployment"
                )

                release.printer.change_head(
                    f"Moving backup {release.backup.path.name} to {release.current.path}"
                )

                if release.backup.path.exists():
                    shutil.move(release.backup.path, release.current.path)

                release.printer.print(
                    f"Moved backup {release.backup.path.name} to {release.current.path}"
                )

                release.printer.change_head(
                    f"Deleting the {release.data.path.name} tangled deployment"
                )

                if release.data.path.exists():
                   shutil.rmtree(release.data.path)

                release.printer.print(
                    f"Deleted the {release.data.path.name} tangled deployment"
                )

            raise e

    def bench_db_and_configs_backup(self):
        self.printer.change_head("Backing up db, common_site_config and site_config.json")

        (self.backup.sites/ self.site_name).mkdir(exist_ok=True,parents=True)
        shutil.copyfile(self.current.common_site_config, self.backup.common_site_config)
        self.bench_backup(self.site_name)
        self.printer.print("Backed up db, common_site_config and site_config.json")

    def create_new_release(self):
        if not self.bench_path.is_symlink():
            if not self.config.configure:
                raise RuntimeError(
                        "Provided bench is not configured. Please use `configure` subcommand for this."
                    )
        else:
            self.config.configure = False

        self.printer.print(f'Bench: {self.config.bench_name} Site: {self.config.site_name}')

        # create new release dirs
        self.printer.change_head("Configuring new release dirs")

        if not self.config.configure:
            self.bench_db_and_configs_backup()

        if self.config.fm:
            if self.config.fm.restore_db_from_site:
                if not self.config.restore_db_file_path:
                    self.config.restore_db_file_path = self.bench_backup(
                        self.config.fm.restore_db_from_site, using_bench_backup=False,compress=True,sql_delete_after_compress=False
                    )

        for dir in [self.new.path, self.new.apps, self.new.sites]:
            dir.mkdir(exist_ok=True)
            self.printer.print(f"Created dir [blue]{dir.name}[/blue] ")

        if self.config.configure:
            if self.config.maintenance_mode:
                start_time = time.time()

                self.printer.print("Enabled maintenance mode")
                self.current.maintenance_mode(self.site_name, True)

            DeploymentManager.configure(config=self.config, only_move=True,backups=True)

            self.printer.change_head(
                "Moving bench directory, creating initial release"
            )

            shutil.move(
                str(self.current.path.absolute()), str(self.path / 'prev_frappe_bench')
            )

            self.bench_path.symlink_to(
                get_relative_path(self.bench_path, self.new.path), True
            )


        self.configure_symlinks()

        self.clone_apps(self.new)

        self.python_env_create(self.new)

        self.bench_setup_requiments(self.new)
        self.bench_build(self.new)

        self.bench_clear_cache(self.current,True)

        if self.config.maintenance_mode:
            start_time = time.time()

            self.printer.print("Enabled maintenance mode")
            self.current.maintenance_mode(self.site_name, True)

        self.sync_configs_with_files(self.config.site_name)

        exception = None

        try:
            self.bench_symlink_and_restart(self.new)

            if self.config.restore_db_file_path:
                self.bench_restore(self.config.restore_db_file_path)

                if self.config.fm:
                    if self.config.fm.restore_db_from_site:
                        if self.config.restore_db_file_path.exists():
                            self.config.restore_db_file_path.unlink()
                            self.printer.print(f'Deleted temporary exported db file {self.config.restore_db_file_path.name}')

                if self.config.fm:
                    if self.config.fm.restore_db_from_site:
                        self.sync_db_encryption_key_from_site(self.config.fm.restore_db_from_site,self.config.fm.restore_db_from_site)

                self.site_installed_apps = self.get_site_installed_apps(self.current)

            self.bench_install_and_migrate(self.current)

        except Exception as e:
            if self.config.rollback:
                exception = e
                self.printer.error(f"Failed to create new release {self.new.path.name}")
                self.printer.stdout.print(Rule(title=f"Rolling back to previous release: {self.previous_release_dir.name}"))

                if self.bench_path.exists():
                    self.bench_path.unlink()

                self.bench_symlink_and_restart(BenchDirectory(self.previous_release_dir))
                self.printer.print("Symlinked previous deployment before new release")

            self.bench_install_and_migrate(self.current)

        self.current.maintenance_mode(self.site_name, False)

        if self.config.maintenance_mode:
            self.printer.print("Disabled maintenance mode")

            if self.config.verbose:
                end_time = time.time()
                elapsed_time = end_time - start_time
                self.printer.print(f"Maintenance Mode Time: {elapsed_time:.2f} seconds",emoji_code=':robot_face:')

        self.cleanup_releases()

        if exception:
            self.printer.error(f"The following error caused the script to rollback changes from {self.previous_release_dir} -> {self.new.path.name}")
            raise exception

    def cleanup_releases(self):

        retain_limit = self.config.releases_retain_limit

        self.printer.change_head(f"Retaining {retain_limit} and cleaning up releaseas")

        retain_limit  += 1

        release_dirs = [d for d in self.path.iterdir() if d.is_dir() and d.name.startswith(RELEASE_DIR_NAME)]

        release_dirs.sort(key=lambda d: self.extract_timestamp(d.name), reverse=True)

        current_release_bench_path = self.bench_path.resolve()

        if current_release_bench_path in release_dirs:
            release_dirs.remove(current_release_bench_path)
            release_dirs.insert(0, current_release_bench_path)

        if self.previous_release_dir in release_dirs and not self.previous_release_dir == current_release_bench_path:
            release_dirs.remove(self.previous_release_dir)
            release_dirs.insert(1, self.previous_release_dir)

        retain_releases_dirs = release_dirs[:retain_limit]

        for dir in retain_releases_dirs:
            release_dirs.remove(dir)

        for dir_to_remove in release_dirs:
            shutil.rmtree(dir_to_remove)

        deleted_dir_names = ' '.join([d.name for d in release_dirs])

        if deleted_dir_names:
            self.printer.print(f"Deleted releases [blue]{deleted_dir_names}[/blue]")

        self.printer.start("Working")

    def extract_timestamp(self, dir_name: str) -> int:
        try:
            timestamp_str = dir_name.split('_')[-1]
            return int(timestamp_str)
        except ValueError:
            return 0

    def clone_apps(self, bench_directory: 'BenchDirectory'):
        for app in self.apps:
            self.printer.change_head(f"Cloning repo {app.repo}")
            bench_directory.clone_app(app)

            app_name = bench_directory.get_app_python_module_name(
                bench_directory.apps / app.dir_name
            )

            from_dir = bench_directory.apps / app.dir_name
            to_dir = bench_directory.apps / app_name

            shutil.move(str(from_dir),str(to_dir))

            self.printer.print(
                f"{'Remote removed ' if app.remove_remote else ''}Cloned Repo: {app.repo}, Module Name: '{app_name}'"
            )

    def get_mariadb_bench_client(self):
        compose_file: ComposeFile = ComposeFile(self.path.parent / "docker-compose.yml")
        compose_project: ComposeProject = ComposeProject(
            compose_file_manager=compose_file
        )

        services_manager: MigrationServicesManager = MigrationServicesManager(
            services_path=CLI_DIR / "services"
        )

        server_db_info: DatabaseServerServiceInfo = (
            DatabaseServerServiceInfo.import_from_compose_file(
                "global-db", services_manager.compose_project
            )
        )
        mariadb_client = MariaDBManager(
            database_server_info=server_db_info,
            compose_project=compose_project,
            run_on_compose_service="frappe",
        )

        return mariadb_client

    def bench_backup(self, site_name: str, file_name: Optional[str] = None, using_bench_backup: bool = True, compress: bool = True, sql_delete_after_compress: bool = True) -> Optional[Path]:
        """Return backup host path"""

        self.printer.change_head(f"Exporting {site_name} db")

        file_name = f"{site_name if file_name is None else file_name}.sql.gz"

        host_backup_config_path = self.backup.path / 'site_config.json'

        host_backup_db_path = self.backup.path / file_name

        backup_config_path = str(host_backup_config_path.absolute())
        backup_db_path = str(host_backup_db_path.absolute())


        if self.mode == 'fm':
            backup_db_path = (
                f"/workspace/{'/'.join(self.backup.path.parts[-2:])}/{file_name}"
            )
            backup_config_path = (
                f"/workspace/{'/'.join(self.backup.path.parts[-2:])}/site_config.json"
            )


        if using_bench_backup:
            db_export_command = [self.bench_cli,'backup','--backup-path-conf', backup_config_path, '--backup-path-db', backup_db_path ]

            output = self.host_run(
                db_export_command,
                self.current,
                #stream=True,
                container=self.mode == "fm",
                capture_output=True)

            return host_backup_db_path

        backup_bench = MigrationBench(name=site_name, path=self.path.parent)
        backup_bench_db_info = backup_bench.get_db_connection_info()

        bench_db_name = backup_bench_db_info.get("name")
        mariadb_client = self.get_mariadb_bench_client()

        host_backup_db_path = host_backup_db_path.parent / host_backup_db_path.name.rstrip('.gz')

        self.backup.path.mkdir(exist_ok=True,parents=True)

        backup_db_path = backup_db_path.rstrip('.gz')

        output = mariadb_client.db_export(bench_db_name, export_file_path=backup_db_path)

        self.printer.print(f"Exported {site_name} db")

        if compress:
            self.printer.change_head(f"Compress {site_name} db")
            with open(host_backup_db_path, 'rb') as f_in:
                import gzip
                with gzip.open(str(host_backup_db_path) + '.gz', 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

            if sql_delete_after_compress:
                if host_backup_db_path.exists():
                    host_backup_db_path.unlink()

            self.printer.print(f"DB has been compressed.")

        return host_backup_db_path


    def bench_restore(self, db_file_path: Path):

        if self.mode == 'host':
            self.printer.warning("db restore is not implemented in host mode")
            return

        # Check if the input file is a .gz file
        if db_file_path.suffix == '.gz':
            self.printer.change_head(f"Decompressing {db_file_path}")
            with gzip.open(db_file_path, 'rb') as f_in:
                decompressed_path = db_file_path.with_suffix('')  # Remove .gz suffix
                with open(decompressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            db_file_path = decompressed_path  # Update db_file_path to the decompressed file

        backup_bench = MigrationBench(name=self.site_name, path=self.path.parent)

        self.printer.change_head(
            f"Restoring {self.site_name} with db from {db_file_path}"
        )

        backup_bench_db_info = backup_bench.get_db_connection_info()

        bench_db_name = backup_bench_db_info.get("name")

        mariadb_client = self.get_mariadb_bench_client()

        mariadb_client.db_import(
            db_name=bench_db_name, host_db_file_path=db_file_path
        )
        self.printer.print(f"Restored {self.site_name} with db from {db_file_path}")

    def sync_db_encryption_key_from_site(self, from_bench_name: str, from_site_name: str):
        self.printer.change_head(f"Copying db_encryption_key from {from_bench_name},if exists")

        site_config_path = (
            self.path.parent
            / from_bench_name
            / "workspace"
            / "frappe-bench"
            / "sites"
            / from_site_name
            / "site_config.json"
        )
        site_config_data = get_json(site_config_path)
        db_encryption_key = site_config_data.get('db_encryption_key', None)

        if db_encryption_key:
            current_site_config_path = self.current.sites / self.site_name / 'site_config.json'
            update_json_keys_in_file_path(current_site_config_path,{"db_encryption_key": db_encryption_key})
            self.printer.change_head(f"Copyied db_encryption_key from {from_bench_name}")


    def sync_configs_with_files(self, site_name: str):
        self.printer.change_head(f"Updating common_site_config.json, site_config.json")
        common_site_config_path = self.current.sites / "common_site_config.json"

        site_config_path = (
            self.current.sites
            / site_name
            / "site_config.json"
        )

        if self.config.common_site_config:
            update_json_keys_in_file_path(common_site_config_path, self.config.common_site_config)

        if self.config.site_config:
            update_json_keys_in_file_path(site_config_path, self.config.site_config)

        self.printer.print(f"Updated common_site_config.json, site_config.json")

    def bench_clear_cache(self, bench_directory: BenchDirectory, website_cache: bool = False):
        clear_cache_command = [self.bench_cli, 'clear-cache']
        clear_website_cache_command = [self.bench_cli, 'clear-website-cache']

        self.printer.change_head(f"Clearing cache{' and website cache' if website_cache else ''}")
        for command in [clear_cache_command,clear_website_cache_command]:
            self.host_run(
                command,
                bench_directory,
                #stream=True,
                container=self.mode == "fm",
                capture_output=False,
            )
            self.printer.print(f"{' '.join(command)} done")

    def bench_install_and_migrate(
        self,
        bench_directory: BenchDirectory,
    ):
        apps = [d for d in bench_directory.apps.iterdir() if d.is_dir()]

        app: Union[AppConfig, Path]

        if self.config.run_bench_migrate:
            self.printer.change_head("Running bench migrate")
            bench_migrate = [self.bench_cli, "migrate"]
            self.host_run(
                bench_migrate,
                bench_directory,
                #stream=True,
                container=self.mode == "fm",
                capture_output=False,
            )
            self.printer.print("Bench migrate done")
        else:
            self.printer.print("Skipped. Bench bench migrate")

        for app in apps:
            app_path = bench_directory.apps / app.name
            app_python_module_name = bench_directory.get_app_python_module_name(
                app_path
            )
            if self.is_app_installed_in_site(
                site_name=self.site_name, app_name=app_python_module_name
            ):
                self.printer.print(
                    f"App {app_python_module_name} is already installed."
                )
                continue

            install_command = [
                self.bench_cli,
                "--site",
                self.site_name,
                "install-app",
                app_python_module_name,
            ]
            self.printer.change_head(
                f"Installing app {app_python_module_name} in {self.site_name}"
            )
            output = self.host_run(
                install_command,
                bench_directory,
                #stream=False,
                container=self.mode == "fm",
                capture_output=True,
            )

            if f"App {app_python_module_name} already installed" in output.combined:
                self.printer.print(
                    f"App {app_python_module_name} is already installed."
                )

            self.printer.print(
                f"Installed app {app_python_module_name} in {self.site_name}"
            )

    def host_run(
        self,
        command: list[str],
        bench_directory: BenchDirectory,
        container: bool = False,
        container_service: str = "frappe",
        container_user: str = "frappe",
        capture_output: bool = True,
    ) -> Union[Iterable[Tuple[str, bytes]], SubprocessOutput]:
        if self.verbose:
            start_time = time.time()

        if not container:
            if capture_output:
                output = run_command_with_exit_code(
                    command,
                    stream=not capture_output,
                    capture_output=capture_output,
                    cwd=str(bench_directory.path.absolute()),
                )

                if self.verbose:
                    end_time = time.time()
                    elapsed_time = end_time - start_time
                    self.printer.print(
                        f"Time Taken: {elapsed_time:.2f} sec, Command: '{' '.join(command)}'",
                        emoji_code=":robot_face:"
                    )
                return output

            else:
                output = run_command_with_exit_code(
                    command,
                    stream=not capture_output,
                    capture_output=capture_output,
                    cwd=str(bench_directory.path.absolute()),
                )

                self.printer.live_lines(output)

                if self.verbose:
                    end_time = time.time()
                    elapsed_time = end_time - start_time
                    self.printer.print(
                        f"Time Taken: {elapsed_time:.2f} sec, Command: '{' '.join(command)}'",
                        emoji_code=":robot_face:"
                    )
                return None

        docker_command = " ".join(command)

        workdir = f"/workspace/{bench_directory.path.name}"

        compose_file: ComposeFile = ComposeFile(self.path.parent / "docker-compose.yml")
        compose_project: ComposeProject = ComposeProject(
            compose_file_manager=compose_file
        )

        if capture_output:
            output: SubprocessOutput = compose_project.docker.compose.exec(
                service=container_service,
                command=docker_command,
                user=container_user,
                workdir=workdir,
                stream=not capture_output,
            )

            if self.verbose:
                end_time = time.time()
                elapsed_time = end_time - start_time
                self.printer.print(
                    f"Time Taken: {elapsed_time:.2f} sec, Command: '{' '.join(command)}'",
                    emoji_code=":robot_face:",
                )

            return output

        else:
            output: Iterable[Tuple[str, bytes]] = compose_project.docker.compose.exec(
                service=container_service,
                command=docker_command,
                user=container_user,
                workdir=workdir,
                stream=not capture_output,
            )
            self.printer.live_lines(output)

            if self.verbose:
                end_time = time.time()
                elapsed_time = end_time - start_time
                self.printer.print(
                    f"Time Taken: {elapsed_time:.2f} sec, Command: '{' '.join(command)}'",
                    emoji_code=":robot_face:",
                )

    def configure_uv(self, bench_directory: BenchDirectory):

        if self.config.uv:
            try:
                output = self.host_run(
                    ["pip", "install", "uv"],
                    bench_directory,
                    #stream=False,
                    container=self.mode == "fm",
                    capture_output=True,
                )
            except DockerException:
                shutil.rmtree(bench_directory.env)
                self.python_env_create(bench_directory)

    def python_env_create(
            self, bench_directory: BenchDirectory, venv_path: str = 'env', python_version: Optional[str] = None
    ):
        python_version = self.config.python_version if self.config.python_version else "3"

        venv_create_command = [f"python{python_version}", "-m", "venv", venv_path]

        self.printer.change_head(
            f"Creating python venv {'using uv' if self.config.uv else ''}"
        )

        if self.config.uv:
            # install uv
            output = self.host_run(
                ["pip", "install", "uv"],
                bench_directory,
                #stream=False,
                container=self.mode == "fm",
                capture_output=True,
            )
            venv_create_command = [
                "uv",
                "venv",
                "--python",
                f"python{python_version}",
                venv_path,
            ]

        output = self.host_run(
            venv_create_command,
            bench_directory,
            #stream=False,
            container=self.mode == "fm",
            capture_output=True,
        )

        pkg_install = [f"{venv_path}/bin/python", "-m", "pip", "install", "wheel"]

        if self.config.uv:
            pkg_install = [
                "uv",
                "pip",
                "install",
                "--python",
                f"{venv_path}/bin/python",
                "-U",
                "pip",
            ]

        output = self.host_run(
            pkg_install,
            bench_directory,
            #stream=False,
            container=self.mode == "fm",
            capture_output=True,
        )
        output = self.host_run(
            [f"{venv_path}/bin/python", "--version"],
            bench_directory,
            #stream=False,
            container=self.mode == "fm",
            capture_output=True,
        )
        self.printer.print(
            f"Created {output.combined[-1]} env {'using uv' if self.config.uv else ''}"
        )

    def bench_install_all_apps_in_python_env(self, bench_directory: BenchDirectory):
        self.printer.change_head(
            f"Installing all apps in python env {'using uv' if self.config.uv else ''}"
        )

        install_cmd = [self.bench_cli, "setup", "requirements", "--python"]

        if self.config.uv:
            install_cmd = [
                "uv",
                "pip",
                "install",
                "--python",
                "env/bin/python",
                "-U",
                "-e",
            ]
            apps = [d for d in bench_directory.apps.iterdir() if d.is_dir()]
            for app in apps:
                self.host_run(
                    install_cmd + [f"apps/{app.name}"],
                    bench_directory,
                    #stream=False,
                    container=self.mode == "fm",
                    capture_output=False,
                )
        else:
            self.host_run(
                install_cmd,
                bench_directory,
                #stream=False,
                container=self.mode == "fm",
                capture_output=False,
            )

        self.printer.print("Installed apps in python env")

    def bench_setup_requiments(self, bench_directory: BenchDirectory):
        node_cmd = [self.bench_cli, "setup", "requirements", "--node"]

        self.printer.change_head("Installing all apps node packages")

        output = self.host_run(
            node_cmd,
            bench_directory,
            #stream=True,
            container=self.mode == "fm",
            capture_output=False,
        )

        self.printer.print("Installed all apps node packages")

        start_time = time.time()

        self.bench_install_all_apps_in_python_env(bench_directory)

        end_time = time.time()
        elapsed_time = end_time - start_time
        self.printer.print(f"Apps python env install time: {elapsed_time:.2f} seconds")

        self.printer.change_head("Configuring apps.txt")
        # Get all directory names in bench_directory.apps
        apps_dir = bench_directory.apps
        app_names = [d.name for d in apps_dir.iterdir() if d.is_dir()]

        # Save the list to bench_directory.sites / 'apps.txt'
        apps_txt_path = bench_directory.sites / "apps.txt"
        apps_txt_path.parent.mkdir(
            parents=True, exist_ok=True
        )  # Ensure the directory exists

        with apps_txt_path.open("w") as f:
            for app_name in app_names:
                app_name = bench_directory.get_app_python_module_name(
                    bench_directory.apps / app_name
                )
                f.write(f"{app_name}\n")
        self.printer.print("Configured apps.txt")

    def bench_build(self, bench_directory: BenchDirectory):
        #apps: list[Union[AppConfig, Path]] = self.apps

        apps = [d for d in bench_directory.apps.iterdir() if d.is_dir()]

        for app in apps:
            self.printer.change_head(f"Building app {app.name}")
            build_cmd = [self.bench_cli, "build","--app", app.name]
            self.host_run(
                build_cmd,
                bench_directory,
                #stream=False,
                container=self.mode == "fm",
                capture_output=False,
            )
            self.printer.print(f"Builded app {app.name}")
        self.printer.print("Builded all apps")

    def bench_symlink_and_restart(self, bench_directory: BenchDirectory):
        self.printer.change_head("Symlinking and restarting")

        if self.bench_path.exists():
            self.bench_path.unlink()

        self.bench_path.symlink_to(
            get_relative_path(self.bench_path, bench_directory.path), True
        )


        start_time = time.time()

        if self.mode == "fm":
            from frappe_manager.commands import app
            try:
                app(['restart', self.site_name])
            except SystemExit:
                pass
        else:
            services_to_restart = ['workers', 'redis', 'web']

            for service in services_to_restart:
                command = ["sudo", "supervisorctl", "restart", f"frappe-bench-{service}:"]
                self.host_run(
                    command,
                    bench_directory,
                    #stream=False,
                    container=False,
                    capture_output=False,
                )

        if self.config.verbose:
            end_time = time.time()
            elapsed_time = end_time - start_time
            self.printer.print(f"Frappe Services Restart Time Taken: {human_readable_time(elapsed_time)}", emoji_code = ":robot_face:")

        self.printer.start("Working")
        self.printer.print("Symlinked and restarted")

    def get_site_installed_apps(self, bench_directory: BenchDirectory):
        command = [self.bench_cli, "list-apps", "-f", "json"]
        try:
            output = self.host_run(
                command,
                bench_directory,
                #stream=False,
                container=self.mode == "fm",
                capture_output=True,
            )
        except DockerException as e:
            self.printer.warning(
                f"Not able to get current list of apps installed in {self.site_name}"
            )
            return {self.site_name: []}
        return json.loads("".join(output.combined))

    def is_app_installed_in_site(self, site_name: str, app_name: str) -> bool:
        site_apps = self.site_installed_apps.get(site_name)

        if not site_apps:
            return False

        if app_name in site_apps:
            return True

        return False
