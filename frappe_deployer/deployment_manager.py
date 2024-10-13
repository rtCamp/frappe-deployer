import shutil
import time
from typing import Iterable, Optional, Tuple, Union, Literal
from frappe_manager.logger.log import richprint
from frappe_manager.utils.helpers import json
from pathlib import Path

from frappe_deployer.config.app import AppConfig
from frappe_deployer.config.config import Config
from frappe_deployer.consts import BACKUP_DIR_NAME, DATA_DIR_NAME, RELEASE_SUFFIX
from frappe_deployer.helpers import get_relative_path
from frappe_deployer.release_directory import BenchDirectory

from frappe_manager.utils.docker import DockerException, SubprocessOutput, run_command_with_exit_code
from frappe_manager.compose_manager.ComposeFile import ComposeFile
from frappe_manager.compose_project.compose_project import ComposeProject

class DeploymentManager:
    apps: list[AppConfig]
    path: Path
    verbose: bool = False
    mode: Literal['fm','host'] = 'host'

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
        self.new = BenchDirectory(self.path / RELEASE_SUFFIX )

        self.printer.start('Working')


    def configure_symlinks(self):
        self.printer.change_head(f'Configuring symlinks')

        # all sites symlink
        for site in self.data.list_sites():
            new_site_path = self.new.sites / site.name
            data_site_path = self.data.sites / site.name
            new_site_path.symlink_to(get_relative_path(new_site_path, data_site_path), True)
            self.printer.print(f'Symlink {site.name}')

        # common_site_config.json
        if not self.data.common_site_config.exists():
            raise RuntimeError(f"{self.data.common_site_config.absolute()} doesn't exist. Please Check")

        self.new.common_site_config.symlink_to(get_relative_path(self.new.common_site_config,self.data.common_site_config), True)
        self.printer.print(f'Symlink [blue]{self.new.common_site_config.name}[/blue] ')

        # config
        if not self.data.config.exists():
            raise RuntimeError(f"{self.data.config.absolute()} doesn't exist. Please Check")

        self.new.config.symlink_to(get_relative_path(self.new.config,self.data.config), True)
        self.printer.print(f'Symlink [blue]{self.new.config.name}[/blue] ')

        # logs
        if not self.data.logs.exists():
            self.printer.print("logs directory doesn't exists recreating it")
            self.data.logs.mkdir(parents=True)

        self.new.logs.symlink_to(get_relative_path(self.new.logs,self.data.logs), True)
        self.printer.print(f'Symlink [blue]{self.new.logs.name}[/blue] ')

    @staticmethod
    def configure(config: Config):
        release =  DeploymentManager(config)

        if release.current.path.is_symlink():
            raise Exception(f'{release.current.path} is symlink.')

        try:
            release.printer.change_head('Creating backup')
            shutil.copytree(config.bench_path, release.backup.path,symlinks=True)
            release.printer.print("Backup completed")

            if not release.data.path.exists():
                release.printer.change_head('Creating release data dir')
                release.data.path.mkdir()
                release.printer.print('Created release data dir')

            # move all sites
            release.printer.change_head('Moving sites into data dir')
            for site in release.current.list_sites():
                new_site_path = release.new.sites / site.name
                data_site_path = release.data.sites / site.name
                shutil.move(str(site.absolute()), str(data_site_path.absolute()))
                site.symlink_to(get_relative_path(new_site_path, data_site_path), True)
                release.printer.print(f'Moved {site.name} and created symlink')

            # common_site_config.json
            if release.current.common_site_config.exists():
                release.printer.change_head('Moving common_site_config.json into data dir')
                shutil.move(str(release.current.common_site_config.absolute()),(release.data.common_site_config.absolute()))
                release.current.common_site_config.symlink_to(get_relative_path(release.new.common_site_config,release.data.common_site_config), True)
                release.printer.print('Moved common_site_config.json and created symlink')

            # logs
            if release.current.logs.exists():
                release.printer.change_head('Moving logs into data dir')
                shutil.move(str(release.current.logs.absolute()),str(release.data.logs.absolute()))
                release.current.logs.symlink_to(get_relative_path(release.new.logs,release.data.logs), True)
                release.printer.print('Moved logs and created symlink')

            # config
            if release.current.config.exists():
                release.printer.change_head('Moving logs into data dir')
                shutil.move(str(release.current.config.absolute()),str(release.data.config.absolute()))
                release.current.config.symlink_to(get_relative_path(release.new.config,release.data.config), True)
                release.printer.print('Moved logs and created symlink')

            # bench
            release.printer.change_head(f'Moving bench directory, creating initial release')
            shutil.move(str(release.current.path.absolute()), str(release.new.path.absolute()))

            release.configure_uv(release.new)
            release.bench_setup_requiments(release.new)
            release.bench_symlink_and_restart(release.new)

            release.bench_build(release.new)
            release.bench_install_and_migrate(release.current,app_name_from_apps_directory=True)

        except Exception as e:
            release.printer.print(f'Rollback\n{"--"*10} ')
            release.printer.change_head(f'Deleting the {release.current.path.name} tangled deployment')

            if release.current.path.exists():
                if release.current.path.is_symlink():
                    release.current.path.unlink()
                else:
                    shutil.rmtree(release.current.path)

            release.printer.print(f'Deleted the {release.current.path.name} tangled deployment')

            release.printer.change_head(f'Moving backup {release.backup.path.name} to {release.current.path}')
            if release.backup.path.exists():
                shutil.move(release.backup.path,release.current.path)

            release.printer.print(f'Moved backup {release.backup.path.name} to {release.current.path}')

            release.printer.change_head(f'Deleting the {release.data.path.name} tangled deployment')
            if release.data.path.exists():
                 shutil.rmtree(release.data.path)

            release.printer.print(f'Deleted the {release.data.path.name} tangled deployment')
            raise e

    def create_new_release(self):

        if not self.bench_path.is_symlink():
            raise RuntimeError(f"Provided bench is not configured. Please use `configure` subcommand for this.")

        # create new release dirs
        self.printer.change_head(f'Configuring new release dirs')
        self.db_and_site_config_backup(self.current)

        for dir in [self.new.path,self.new.apps,self.new.sites]:
            dir.mkdir(exist_ok=True)
            self.printer.print(f'Created dir [blue]{dir.name}[/blue] ')

        self.configure_symlinks()
        self.clone_apps(self.new)

        self.python_env_create(self.new)

        self.bench_setup_requiments(self.new)
        self.bench_build(self.new)

        if self.config.maintenance_mode:
            start_time = time.time()

            self.printer.print("Enabled maintenance mode",)
            self.current.maintenance_mode(self.site_name,True)

        self.bench_symlink_and_restart(self.new)
        self.bench_install_and_migrate(self.current)

        self.current.maintenance_mode(self.site_name,False)

        if self.config.maintenance_mode:
            self.printer.print("Disabled maintenance mode",)
            end_time = time.time()
            elapsed_time = end_time - start_time
            self.printer.print(f"Maintenance Mode Time: {elapsed_time:.2f} seconds")

    def clone_apps(self, bench_directory: BenchDirectory):
        for app in self.apps:
            self.printer.change_head(f"Cloning repo {app.repo_url}")
            bench_directory.clone_app(app)
            app_name = bench_directory.get_app_python_module_name(bench_directory.apps / app.dir_name)
            self.printer.print(f"Cloned Repo: {app.repo_url}, Module Name: '{app_name}'")

    def bench_install_and_migrate(self, bench_directory: BenchDirectory, app_name_from_apps_directory: bool = False):
        apps: list[Union[AppConfig,Path]] =  self.apps

        if app_name_from_apps_directory:
            apps  = [ d for d in bench_directory.apps.iterdir() if d.is_dir()]

        app: Union[AppConfig,Path]

        self.printer.change_head("Running bench migrate")
        bench_migrate = ['bench','migrate']
        self.host_run(bench_migrate, bench_directory, stream=True,container= self.mode == 'fm', capture_output=False)
        self.printer.print(f"Bench migrate done")

        for app in apps:
            app_name = app.name if app_name_from_apps_directory else app.dir_name
            app_path = bench_directory.apps / app_name
            app_python_module_name = bench_directory.get_app_python_module_name(app_path)

            if self.is_app_installed_in_site(site_name=self.site_name,app_name=app_python_module_name):
                self.printer.print(f"App {app_python_module_name} is already installed.")
                continue

            install_command = ['bench','--site',self.site_name, 'install-app', app_python_module_name]
            self.printer.change_head(f"Installing app {app_python_module_name} in {self.site_name}")
            output = self.host_run(install_command, bench_directory, stream=False,container= self.mode == 'fm', capture_output=True)

            if f'App {app_python_module_name} already installed' in output.combined:
                self.printer.print(f"App {app_python_module_name} is already installed.")

            self.printer.print(f"Installed app {app_python_module_name} in {self.site_name}")


    def host_run(self, command: list[str], bench_directory: BenchDirectory, container: bool = False, container_service: str ='frappe', container_user: str = 'frappe', stream: bool =False, capture_output: bool = True) -> Union[Iterable[Tuple[str, bytes]], SubprocessOutput]:

        if self.verbose: start_time = time.time()

        if not container:
            output = run_command_with_exit_code(
                command, stream=stream, capture_output=capture_output, cwd = str(bench_directory.path.absolute())
            )

            if self.verbose:
                end_time = time.time()
                elapsed_time = end_time - start_time
                self.printer.print(f"Time Taken: {elapsed_time:.2f} sec, Command: '{' '.join(command)}'",emoji_code=':robot_face:')
                return output

        docker_command = " ".join(command)

        workdir = f'/workspace/{bench_directory.path.name}'

        compose_file: ComposeFile = ComposeFile( self.path.parent / 'docker-compose.yml')
        compose_project: ComposeProject = ComposeProject(compose_file_manager=compose_file)

        if capture_output:
            output: SubprocessOutput = compose_project.docker.compose.exec(
                service=container_service, command=docker_command, user=container_user, workdir=workdir, stream=not capture_output
            )

            if self.verbose:
                end_time = time.time()
                elapsed_time = end_time - start_time
                self.printer.print(f"Time Taken: {elapsed_time:.2f} sec, Command: '{' '.join(command)}'",emoji_code=':robot_face:')
                return output
        else:
            output: Iterable[Tuple[str, bytes]] = compose_project.docker.compose.exec(
                service=container_service, command=docker_command, user=container_user, workdir=workdir, stream=not capture_output
            )
            if self.verbose:
                self.printer.live_lines(output)
                end_time = time.time()
                elapsed_time = end_time - start_time
                self.printer.print(f"Time Taken: {elapsed_time:.2f} sec, Command: '{' '.join(command)}'",emoji_code=':robot_face:')


    def configure_uv(self,bench_directory: BenchDirectory):
        if self.config.uv:
            try:
                output = self.host_run(['pip','install','uv'], bench_directory ,stream=False,container= self.mode == 'fm', capture_output=True)
            except DockerException:
                shutil.rmtree(bench_directory.env)
                self.python_env_create(bench_directory)

    def python_env_create(self, bench_directory: BenchDirectory, python_version: Optional[str] = None ):
        python_version = python_version if python_version else ''

        venv_create_command = [f'python{python_version}','-m', 'venv','env']

        self.printer.change_head(f"Creating python venv {'using uv' if self.config.uv else ''}")

        if self.config.uv:
            # install uv
            output = self.host_run(['pip','install','uv'], bench_directory ,stream=False,container= self.mode == 'fm', capture_output=True)
            venv_create_command = [f'uv','venv', '--python',f'python{python_version}','env']

        output = self.host_run(venv_create_command, bench_directory ,stream=False,container= self.mode == 'fm', capture_output=True)

        pkg_install = ['env/bin/python','-m','pip','install','wheel']

        if self.config.uv:
            pkg_install = ['uv','pip','install','--python', 'env/bin/python','-U', 'pip']

        output = self.host_run(pkg_install, bench_directory ,stream=False,container= self.mode == 'fm', capture_output=True)
        output = self.host_run(['env/bin/python','--version'], bench_directory ,stream=False,container= self.mode == 'fm', capture_output=True)
        self.printer.print(f"Created {output.combined[-1]} env {'using uv' if self.config.uv else ''}")

    def bench_install_all_apps_in_python_env(self, bench_directory: BenchDirectory):
        self.printer.change_head(f"Installing all apps in python env {'using uv' if self.config.uv else ''}")

        install_cmd = ['bench','setup','requirements','--python']

        if self.config.uv:
            install_cmd = ['uv','pip','install','--python', 'env/bin/python', '-U','-e']
            apps  = [ d for d in bench_directory.apps.iterdir() if d.is_dir()]
            for app in apps:
                self.host_run(install_cmd + [f'apps/{app.name}'], bench_directory ,stream=False,container= self.mode == 'fm', capture_output=False)
        else:
            self.host_run(install_cmd, bench_directory ,stream=False,container= self.mode == 'fm', capture_output=False)

        self.printer.print("Installed apps in python env")


    def bench_setup_requiments(self, bench_directory: BenchDirectory):
        node_cmd = ['bench','setup','requirements','--node']

        self.printer.change_head("Installing all apps node packages")
        self.host_run(node_cmd, bench_directory ,stream=False,container= self.mode == 'fm', capture_output=False)
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
        apps_txt_path = bench_directory.sites / 'apps.txt'
        apps_txt_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure the directory exists

        with apps_txt_path.open('w') as f:
            for app_name in app_names:
                app_name = bench_directory.get_app_python_module_name(bench_directory.apps / app_name)
                f.write(f"{app_name}\n")
        self.printer.print("Configured apps.txt")

    def bench_build(self, bench_directory: BenchDirectory):
        self.printer.change_head("Building all apps")
        build_cmd = ['bench','build','--force']
        self.host_run(build_cmd, bench_directory ,stream=False,container= self.mode == 'fm', capture_output=False)
        self.printer.print("Builded all apps")

    def db_and_site_config_backup(self, bench_directory: BenchDirectory):
        self.printer.change_head("Taking DB and site_config.json backup")

        backup_dir = str(self.backup.path.absolute())

        if self.mode == 'fm':
            backup_dir = f"/workspace/{'/'.join(self.backup.path.parts[-2:])}"

        command = ['bench','backup', '--backup-path', backup_dir]

        self.host_run(command, bench_directory ,stream=False,container= self.mode == 'fm', capture_output=False)
        self.printer.start('Working')
        self.printer.print("Backup Taken")

    def bench_symlink_and_restart(self, bench_directory: BenchDirectory):

        self.printer.change_head("Symlinking and restarting")

        if self.bench_path.exists():
             self.bench_path.unlink()

        self.bench_path.symlink_to(get_relative_path(self.bench_path, self.new.path), True)

        command = ['bench', 'restart']

        if self.mode == 'fm':
            command = ['fm', 'restart', self.site_name]

        self.printer.stop()
        self.host_run(command, bench_directory ,stream=False, container=False, capture_output=False)
        self.printer.start('Working')
        self.printer.print("Symlinked and restarted")

    def get_site_installed_apps(self, bench_directory: BenchDirectory):
        command = ['bench', 'list-apps','-f','json']
        try:
            output = self.host_run(command, bench_directory, stream=False,container= self.mode == 'fm', capture_output=True)
        except DockerException as e:
            self.printer.warning(f'Not able to get current list of apps installed in {self.site_name}')
            return {self.site_name:[]}
        return json.loads("".join(output.combined))

    def is_app_installed_in_site(self, site_name: str, app_name: str ) -> bool:
        site_apps = self.site_installed_apps.get(site_name)

        if not site_apps:
            return False

        if app_name in site_apps:
            return True

        return False
