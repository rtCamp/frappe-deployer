import shutil
import time
from typing import Iterable, Optional, Tuple, Union, Literal
from frappe_manager import CLI_DIR
from frappe_manager.logger.log import richprint
from frappe_manager.utils.helpers import json
from pathlib import Path

from frappe_deployer.config.app import AppConfig
from frappe_deployer.config.config import Config
from frappe_deployer.consts import (
    BACKUP_DIR_NAME,
    DATA_DIR_NAME,
    RELEASE_DIR_NAME,
    RELEASE_SUFFIX,
)
from frappe_deployer.helpers import get_json, get_relative_path, update_json_keys_in_file_path
from frappe_deployer.release_directory import BenchDirectory

from frappe_manager.utils.docker import (
    DockerException,
    SubprocessOutput,
    run_command_with_exit_code,
)
from frappe_manager.compose_manager.ComposeFile import ComposeFile
from frappe_manager.compose_project.compose_project import ComposeProject
from frappe_manager.services_manager.database_service_manager import (
    DatabaseServerServiceInfo,
    MariaDBManager,
)
from frappe_manager.migration_manager.migration_helpers import (
    MigrationBench,
    MigrationServicesManager,
)


class DeploymentManager:
    apps: list[AppConfig]
    path: Path
    verbose: bool = False
    mode: Literal["fm", "host"] = "host"

    def __init__(self, config: Config) -> None:
        self.config = config
        self.verbose = config.verbose
        self.site_name = config.site_name
        self.bench_path = config.bench_path
        self.apps = config.apps
        self.mode = config.mode
        self.path = config.deploy_dir_path
        self.printer = richprint

        self.current = BenchDirectory(config.bench_path)
        self.site_installed_apps = self.get_site_installed_apps(self.current)

        self.data = BenchDirectory(self.path / DATA_DIR_NAME)
        self.backup = BenchDirectory(self.path / BACKUP_DIR_NAME / RELEASE_SUFFIX)
        self.new = BenchDirectory(self.path / RELEASE_SUFFIX)

        self.previous_release_dir = self.current.path.resolve()

        self.printer.start("Working")

    def configure_symlinks(self):
        self.printer.change_head(f"Configuring symlinks")

        # all sites symlink
        for site in self.data.list_sites():
            new_site_path = self.new.sites / site.name
            data_site_path = self.data.sites / site.name
            new_site_path.symlink_to(
                get_relative_path(new_site_path, data_site_path), True
            )
            self.printer.print(f"Symlink {site.name}")

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

    @staticmethod
    def configure(config: Config):
        release = DeploymentManager(config)

        if release.current.path.is_symlink():
            raise Exception(f"{release.current.path} is symlink.")

        try:
            release.printer.change_head("Creating backup")
            shutil.copytree(config.bench_path, release.backup.path, symlinks=True)
            release.printer.print("Backup completed")

            if not release.data.path.exists():
                release.printer.change_head("Creating release data dir")
                release.data.path.mkdir()
                release.printer.print("Created release data dir")

            # move all sites
            release.printer.change_head("Moving sites into data dir")
            for site in release.current.list_sites():
                new_site_path = release.new.sites / site.name
                data_site_path = release.data.sites / site.name
                shutil.move(str(site.absolute()), str(data_site_path.absolute()))
                site.symlink_to(get_relative_path(new_site_path, data_site_path), True)
                release.printer.print(f"Moved {site.name} and created symlink")

            # common_site_config.json
            if release.current.common_site_config.exists():
                release.printer.change_head(
                    "Moving common_site_config.json into data dir"
                )
                shutil.move(
                    str(release.current.common_site_config.absolute()),
                    str(release.data.common_site_config.absolute()),
                )
                release.current.common_site_config.symlink_to(
                    get_relative_path(
                        release.new.common_site_config, release.data.common_site_config
                    ),
                    True,
                )
                release.printer.print(
                    "Moved common_site_config.json and created symlink"
                )

            # logs
            if release.current.logs.exists():
                release.printer.change_head("Moving logs into data dir")
                shutil.move(
                    str(release.current.logs.absolute()),
                    str(release.data.logs.absolute()),
                )
                release.current.logs.symlink_to(
                    get_relative_path(release.new.logs, release.data.logs), True
                )
                release.printer.print("Moved logs and created symlink")

            # config
            if release.current.config.exists():
                release.printer.change_head("Moving logs into data dir")
                shutil.move(
                    str(release.current.config.absolute()),
                    str(release.data.config.absolute()),
                )
                release.current.config.symlink_to(
                    get_relative_path(release.new.config, release.data.config), True
                )
                release.printer.print("Moved logs and created symlink")

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
            release.bench_install_and_migrate(
                release.current, app_name_from_apps_directory=True
            )

        except Exception as e:
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
        shutil.copyfile(self.current.sites / self.site_name / 'site_config.json', self.backup.sites / self.site_name / 'site_config.json')
        self.bench_backup(self.site_name)
        self.printer.print("Backed up db, common_site_config and site_config.json")

    def create_new_release(self):
        if not self.bench_path.is_symlink():
            raise RuntimeError(
                f"Provided bench is not configured. Please use `configure` subcommand for this."
            )

        self.printer.print(f'Bench: {self.config.bench_name} Site: {self.config.site_name}')

        # create new release dirs
        self.printer.change_head(f"Configuring new release dirs")
        self.bench_db_and_configs_backup()

        if self.config.fm:
            if self.config.fm.db_bench_name:
                if not self.config.restore_db_file_path:
                    self.config.restore_db_file_path = self.bench_backup(
                        self.config.fm.db_bench_name
                    )

        for dir in [self.new.path, self.new.apps, self.new.sites]:
            dir.mkdir(exist_ok=True)
            self.printer.print(f"Created dir [blue]{dir.name}[/blue] ")

        self.configure_symlinks()
        self.clone_apps(self.new)

        self.python_env_create(self.new)

        self.bench_setup_requiments(self.new)
        self.bench_build(self.new)

        if self.config.use_maintenance_mode:
            start_time = time.time()

            self.printer.print("Enabled maintenance mode")
            self.current.maintenance_mode(self.site_name, True)

        self.sync_configs_with_files(self.config.site_name)

        self.bench_symlink_and_restart(self.new)

        if self.config.restore_db_file_path:
            self.bench_restore(self.config.restore_db_file_path)

            if self.config.fm:
                if self.config.fm.db_bench_name:
                    self.sync_db_encryption_key_from_site(self.config.fm.db_bench_name,self.config.fm.db_bench_name)

            self.site_installed_apps = self.get_site_installed_apps(self.current)

        self.bench_clear_cache(self.current,True)
        self.bench_install_and_migrate(self.current)

        self.current.maintenance_mode(self.site_name, False)

        if self.config.use_maintenance_mode:
            self.printer.print("Disabled maintenance mode")
            end_time = time.time()
            elapsed_time = end_time - start_time
            self.printer.print(f"Maintenance Mode Time: {elapsed_time:.2f} seconds")

        self.cleanup_releases()

    def cleanup_releases(self):

        retain_limit = self.config.releases_retain_limit

        self.printer.change_head(f"Retaining {retain_limit} and cleaning up releaseas")

        retain_limit  += 1

        release_dirs = [d for d in self.path.iterdir() if d.is_dir() and d.name.startswith(RELEASE_DIR_NAME)]

        release_dirs.sort(key=lambda d: self.extract_timestamp(d.name), reverse=True)

        if self.previous_release_dir in release_dirs:
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

        self.printer.change_head("Working")

    def extract_timestamp(self, dir_name: str) -> int:
        try:
            timestamp_str = dir_name.split('_')[-1]
            return int(timestamp_str)
        except ValueError:
            return 0

    def clone_apps(self, bench_directory: BenchDirectory):
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


    def bench_backup(self, site_name: str, file_name: Optional[str] = None ) -> Optional[Path]:
        """Return backup host path"""

        if self.config.mode == "fm":
            self.printer.change_head(f"Exporting {site_name} db")

            file_name = f"{site_name if file_name is None else file_name}.sql"

            backup_bench = MigrationBench(name=site_name, path=self.path.parent)
            self.printer.change_head(f"bench backup {site_name}")
            backup_bench_db_info = backup_bench.get_db_connection_info()
            export_path = (
                f"/workspace/{'/'.join(self.backup.path.parts[-2:])}/{file_name}"
            )

            self.backup.path.mkdir(exist_ok=True)

            bench_db_name = backup_bench_db_info.get("name")
            mariadb_client = self.get_mariadb_bench_client()
            mariadb_client.db_export(bench_db_name, export_file_path=export_path)
            self.printer.print(f"Exported {site_name} db")

            return self.backup.path / file_name

        return None

    def bench_restore(self, db_file_path: Path):
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
        clear_cache_command = ['bench', 'clear-cache']
        clear_website_cache_command = ['bench', 'clear-website-cache']

        self.printer.change_head(f"Clearing cache{' and website cache' if website_cache else ''}")
        for command in [clear_cache_command,clear_website_cache_command]:
            self.host_run(
                command,
                bench_directory,
                stream=True,
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
            bench_migrate = ["bench", "migrate"]
            self.host_run(
                bench_migrate,
                bench_directory,
                stream=True,
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
                "bench",
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
                stream=False,
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
        stream: bool = False,
        capture_output: bool = True,
    ) -> Union[Iterable[Tuple[str, bytes]], SubprocessOutput]:
        if self.verbose:
            start_time = time.time()

        if not container:
            output = run_command_with_exit_code(
                command,
                stream=stream,
                capture_output=capture_output,
                cwd=str(bench_directory.path.absolute()),
            )

            if self.verbose:
                end_time = time.time()
                elapsed_time = end_time - start_time
                self.printer.print(
                    f"Time Taken: {elapsed_time:.2f} sec, Command: '{' '.join(command)}'",
                    emoji_code=":robot_face:",
                )
                return output

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
            if self.verbose:
                self.printer.live_lines(output)
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
                    stream=False,
                    container=self.mode == "fm",
                    capture_output=True,
                )
            except DockerException:
                shutil.rmtree(bench_directory.env)
                self.python_env_create(bench_directory)

    def python_env_create(
        self, bench_directory: BenchDirectory, python_version: Optional[str] = None
    ):
        python_version = python_version if python_version else ""

        venv_create_command = [f"python{python_version}", "-m", "venv", "env"]

        self.printer.change_head(
            f"Creating python venv {'using uv' if self.config.uv else ''}"
        )

        if self.config.uv:
            # install uv
            output = self.host_run(
                ["pip", "install", "uv"],
                bench_directory,
                stream=False,
                container=self.mode == "fm",
                capture_output=True,
            )
            venv_create_command = [
                f"uv",
                "venv",
                "--python",
                f"python{python_version}",
                "env",
            ]

        output = self.host_run(
            venv_create_command,
            bench_directory,
            stream=False,
            container=self.mode == "fm",
            capture_output=True,
        )

        pkg_install = ["env/bin/python", "-m", "pip", "install", "wheel"]

        if self.config.uv:
            pkg_install = [
                "uv",
                "pip",
                "install",
                "--python",
                "env/bin/python",
                "-U",
                "pip",
            ]

        output = self.host_run(
            pkg_install,
            bench_directory,
            stream=False,
            container=self.mode == "fm",
            capture_output=True,
        )
        output = self.host_run(
            ["env/bin/python", "--version"],
            bench_directory,
            stream=False,
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

        install_cmd = ["bench", "setup", "requirements", "--python"]

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
                    stream=False,
                    container=self.mode == "fm",
                    capture_output=False,
                )
        else:
            self.host_run(
                install_cmd,
                bench_directory,
                stream=False,
                container=self.mode == "fm",
                capture_output=False,
            )

        self.printer.print("Installed apps in python env")

    def bench_setup_requiments(self, bench_directory: BenchDirectory):
        node_cmd = ["bench", "setup", "requirements", "--node"]

        self.printer.change_head("Installing all apps node packages")
        self.host_run(
            node_cmd,
            bench_directory,
            stream=False,
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
            build_cmd = ["bench", "build","--app", app.name]
            self.host_run(
                build_cmd,
                bench_directory,
                stream=False,
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
            get_relative_path(self.bench_path, self.new.path), True
        )

        command = ["bench", "restart"]

        if self.mode == "fm":
            command = ["fm", "restart", self.site_name]

        self.printer.stop()
        self.host_run(
            command,
            bench_directory,
            stream=False,
            container=False,
            capture_output=False,
        )
        self.printer.start("Working")
        self.printer.print("Symlinked and restarted")

    def get_site_installed_apps(self, bench_directory: BenchDirectory):
        command = ["bench", "list-apps", "-f", "json"]
        try:
            output = self.host_run(
                command,
                bench_directory,
                stream=False,
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
