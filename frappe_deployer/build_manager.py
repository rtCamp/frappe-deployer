import gzip
import shutil
import time
import os
import sys
from pathlib import Path
from typing import Iterable, Optional, Tuple, Union

from frappe_manager.docker_wrapper.DockerClient import DockerClient


def is_ci():
    return os.environ.get("CI", "").lower() == "true"


def is_tty():
    return sys.stdout.isatty()


from frappe_manager.compose_manager.ComposeFile import ComposeFile
from frappe_manager.compose_project.compose_project import ComposeProject
from frappe_manager.logger.log import richprint
from frappe_manager.utils.docker import (
    DockerException,
    SubprocessOutput,
    run_command_with_exit_code,
)
from frappe_manager.utils.helpers import json
from pydantic import BaseModel

from frappe_deployer.config.app import AppConfig
from frappe_deployer.config.config import Config
from frappe_deployer.config.fm import FMConfig
from frappe_deployer.config.host import HostConfig
from frappe_deployer.helpers import (
    get_relative_path,
    human_readable_time,
)
from frappe_deployer.release_directory import BenchDirectory


def log_execution_time(method):
    import functools

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        import time

        start_time = time.time()
        result = method(self, *args, **kwargs)
        end_time = time.time()
        elapsed_time = end_time - start_time
        if getattr(self, "config", None) and getattr(self.config, "verbose", False):
            self.printer.print(
                f"{method.__name__} Time Taken: {human_readable_time(elapsed_time)}", emoji_code=":robot_face:"
            )
        return result

    return wrapper

# TODO: BuildManager and DeploymentManager can be consolidated later on into one

class BuildManager:
    apps: list[AppConfig]
    path: Path
    verbose: bool = False

    def __init__(self, config: Config) -> None:
        self.path = config.bench_path
        self.mode = "fm"
        self.config = config
        self.verbose = config.verbose
        self.bench_path = config.bench_path
        self.apps = config.apps
        self.printer = richprint
        self.bench_cli = "/usr/local/bin/bench"
        self.current = BenchDirectory(config.bench_path)
        self.printer.start("Working")

    def bake(self):
        self.printer.print(f"Bench: {self.config.bench_name}")
        self.current.setup_dir(create_tmps=True)
        self.printer.change_head("Configuring bench dirs")
        self.config.to_toml(self.current.path / "fmd-config.toml")
        self.clone_apps(self.current)
        self.python_env_create(self.current)
        self.bench_setup_requiments(self.current)
        self.bench_build(self.current)

    def extract_timestamp(self, dir_name: str) -> int:
        try:
            timestamp_str = dir_name.split("_")[-1]
            return int(timestamp_str)
        except ValueError:
            return 0

    def clone_apps(
        self,
        bench_directory: "BenchDirectory",
        data_directory: Optional["BenchDirectory"] = None,
        overwrite: bool = False,
        backup=True,
    ):
        clone_map = {}  # (repo, ref) -> clone_path

        for app in self.apps:
            self.printer.change_head(f"Cloning repo {app.repo}")

            if app.symlink:
                key = (app.repo, app.ref)
                if key in clone_map:
                    clone_path = clone_map[key]
                    self.printer.print(f"Reusing clone for {app.repo}@{app.ref} subdir: {app.subdir_path}")
                else:
                    if not data_directory:
                        raise RuntimeError("Deployment data directory is not provided")
                    clone_path = data_directory.get_frappe_bench_app_path(
                        app, append_release_name=bench_directory.path.resolve().name, suffix="_clone"
                    )
                    data_directory.clone_app(app, clone_path=clone_path, move_to_subdir=False)
                    clone_map[key] = clone_path
            else:
                clone_path = bench_directory.get_frappe_bench_app_path(app, suffix="_clone")
                bench_directory.clone_app(app, clone_path=clone_path)

            from_dir = clone_path

            if app.symlink:
                if app.subdir_path:
                    from_dir = from_dir / app.subdir_path

            app_name = app.app_name if app.app_name else bench_directory.get_app_python_module_name(from_dir)
            to_dir = bench_directory.apps / app_name

            import datetime

            if to_dir.exists():
                if not overwrite:
                    raise FileExistsError(
                        f"App directory '{to_dir}' already exists. Use \"--overwrite\" to overwrite it."
                    )

                archive_base = bench_directory.path / "archived" / "apps"
                archive_base.mkdir(parents=True, exist_ok=True)
                date_str = datetime.datetime.now().strftime("%Y-%m-%d")
                archive_path = archive_base / f"{to_dir.name}-{date_str}"
                shutil.move(str(to_dir), str(archive_path))
                self.printer.print(f"Archived existing app to {archive_path}")

                if not backup:
                    shutil.rmtree(str(archive_path))

            if app.symlink:
                symlink_path = get_relative_path(to_dir, from_dir)
                to_dir.symlink_to(symlink_path, True)
            else:
                shutil.move(str(from_dir), str(to_dir))

            self.printer.print(
                f"{'Remote removed ' if app.remove_remote else ''}Cloned Repo: {app.repo}, Module Name: '{app_name}'"
            )

    def get_script_env(self, app_name: Optional[str] = None) -> dict[str, str]:
        """Get environment variables for scripts with config values"""
        env = {}

        # Add computed properties first
        computed_props = {
            "BENCH_PATH": str(self.bench_path),
            "DEPLOY_PATH": str(self.config.deploy_dir_path),
            "APPS": ",".join(d.name for d in self.current.apps.iterdir() if d.is_dir()),
        }

        # Add app-specific environment variables if an app name is provided
        if app_name:
            computed_props.update(
                {"APP_NAME": app_name, "APP_PATH": f"/workspace/{self.bench_path.name}/apps/{app_name}"}
            )

        env.update(computed_props)

        # Get all fields from Config class
        config_fields = self.config.__class__.model_fields

        # Add environment variables for each config field
        for field_name, field in config_fields.items():
            value = getattr(self.config, field_name, None)
            if value is not None:  # Skip None values
                env_key = field_name.upper()

                # Handle different types of values
                if isinstance(value, list) and value and isinstance(value[0], BaseModel):
                    # Handle list of Pydantic models
                    import json

                    env[env_key] = json.dumps([item.model_dump() for item in value])
                elif isinstance(value, dict):
                    import json

                    env[env_key] = json.dumps(value)
                elif isinstance(value, Path):
                    env[env_key] = str(value)
                elif isinstance(value, bool):
                    env[env_key] = str(value).lower()
                elif isinstance(value, (BaseModel, AppConfig, FMConfig, HostConfig)):
                    # Handle single Pydantic model
                    import json

                    env[env_key] = json.dumps(value.model_dump())
                else:
                    env[env_key] = str(value)

        return env

    def _run_script(
        self,
        script_content: str,
        bench_directory: BenchDirectory,
        script_type: str,
        container: bool = False,
        app_name: Optional[str] = None,
        custom_workdir: Optional[str] = None,
    ) -> None:
        """Execute a shell script with proper setup and cleanup."""
        self.printer.change_head(f"Running {script_type}")

        # Create deployment_tmp directory in bench directory
        script_dir = self.current.path.parent / "deployment_tmp"
        script_dir.mkdir(parents=True, exist_ok=True)

        # Create unique script name
        script_name = f"temp_script_{int(time.time())}.sh"
        script_path = script_dir / script_name

        try:
            # Write script content
            with open(script_path, "w") as script_file:
                script_file.write("set -e\n")  # Remove shebang, just keep error handling
                script_file.write(script_content)

            script_path.chmod(0o755)

            # Adjust script path for container execution
            if container:
                container_script_path = f"/workspace/deployment_tmp/{script_name}"
                # Use custom workdir if provided
                if custom_workdir:
                    workdir = custom_workdir
                else:
                    workdir = "/workspace/deployment_tmp"
            else:
                container_script_path = str(script_path)
                # Use custom workdir if provided
                if custom_workdir:
                    workdir = custom_workdir
                else:
                    workdir = str(script_dir)

            # Get script environment variables with optional app name
            script_env = self.get_script_env(app_name)

            # Execute script using bash explicitly
            output = self.host_run(
                ["bash", container_script_path],
                bench_directory,
                container=container,
                capture_output=True,
                workdir=workdir,
                env=script_env,
            )

            # Print output
            if output and output.combined:
                for line in output.combined:
                    if line.strip():
                        self.printer.print(line.strip())
            self.printer.print(f"{script_type} done")

        finally:
            # Cleanup
            try:
                if script_path.exists():
                    script_path.unlink()
                    if not any(script_dir.iterdir()):  # If directory is empty
                        script_dir.rmdir()  # Remove the deployment_tmp directory
            except Exception as e:
                self.printer.warning(f"Failed to cleanup temporary script: {e}")

    def host_run(
        self,
        command: list[str],
        bench_directory: BenchDirectory,
        container: bool = False,
        container_service: str = "frappe",
        container_user: str = "frappe",
        capture_output: bool = True,
        live_lines: int = 4,
        workdir: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
    ) -> Union[Iterable[Tuple[str, bytes]], SubprocessOutput]:
        if self.verbose:
            start_time = time.time()

        base_env = {"COREPACK_ENABLE_DOWNLOAD_PROMPT":"0"}

        if env:
            base_env.update(env)

        print("fmd - base", base_env)

        if not container:
            if capture_output:
                output = run_command_with_exit_code(
                    command,
                    stream=not capture_output,
                    capture_output=capture_output,
                    cwd=str(bench_directory.path.absolute()),
                    env=base_env,
                )

                if self.verbose:
                    end_time = time.time()
                    elapsed_time = end_time - start_time
                    self.printer.print(
                        f"Time Taken: {elapsed_time:.2f} sec, Command: '{' '.join(command)}'", emoji_code=":robot_face:"
                    )
                return output

            else:
                output = run_command_with_exit_code(
                    command,
                    stream=not capture_output,
                    capture_output=capture_output,
                    cwd=str(bench_directory.path.absolute()),
                )

                if not is_ci() and is_tty():
                    self.printer.live_lines(output, lines=live_lines)
                else:
                    for source, line in output:
                        if isinstance(line, bytes):
                            line = line.decode(errors="replace")
                        self.printer.print(line.rstrip(), emoji_code="")

                if self.verbose:
                    end_time = time.time()
                    elapsed_time = end_time - start_time
                    self.printer.print(
                        f"Time Taken: {elapsed_time:.2f} sec, Command: '{' '.join(command)}'", emoji_code=":robot_face:"
                    )
                return None

        docker_command = " ".join(command)
        docker_entrypoint = f"/bin/bash"
        docker_command = f"-c 'source /etc/bash.bashrc; {docker_command}'"

        workdir = workdir or f"/workspace/{bench_directory.path.name}"

        if self.config.build:
            workdir = "/workspace/frappe-bench"

        compose_file: ComposeFile = ComposeFile(self.path.parent / "docker-compose.yml")
        compose_project: ComposeProject = ComposeProject(compose_file_manager=compose_file)

        if capture_output:
            if self.config.build:
                output = DockerClient().run(
                    image=self.config.build.image,
                    user=self.config.build.user,
                    command=docker_command,
                    workdir=workdir,
                    env=base_env,
                    entrypoint=docker_entrypoint,
                    pull="missing",
                    volume=f"{self.path}:/workspace/frappe-bench",
                    stream=not capture_output,
                    rm=True,
                )
            else:
                output: SubprocessOutput = compose_project.docker.compose.exec(
                    service=container_service,
                    command=docker_entrypoint + docker_command,
                    user=container_user,
                    workdir=workdir,
                    stream=not capture_output,
                    env=base_env,  # Pass formatted list for docker execution
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
            if self.config.build:
                output = DockerClient().run(
                    image=self.config.build.image,
                    user=self.config.build.user,
                    workdir=workdir,
                    command=docker_command,
                    env=base_env,
                    entrypoint=docker_entrypoint,
                    pull="missing",
                    volume=f"{self.path}:/workspace/frappe-bench",
                    stream=not capture_output,
                    rm=True,
                )
            else:
                output: Iterable[Tuple[str, bytes]] = compose_project.docker.compose.exec(
                    service=container_service,
                    command=docker_command,
                    user=container_user,
                    workdir=workdir,
                    stream=not capture_output,
                    env=base_env,  # Pass formatted list for docker execution
                )

            if not is_ci() and is_tty():
                self.printer.live_lines(output, lines=live_lines)
            else:
                for source, line in output:
                    if isinstance(line, bytes):
                        line = line.decode(errors="replace")
                    self.printer.print(line.rstrip(), emoji_code="")

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
                # First check if uv is already installed
                check_uv = None
                try:
                    check_uv = self.host_run(
                        ["which", "uv"],
                        bench_directory,
                        container=self.mode == "fm",
                        capture_output=True,
                    )
                except DockerException:
                    pass

                # If which command returns nothing, uv is not installed
                if not check_uv or not check_uv.combined:
                    output = self.host_run(
                        ["pip", "install", "uv"],
                        bench_directory,
                        container=self.mode == "fm",
                        capture_output=True,
                    )
            except DockerException:
                shutil.rmtree(bench_directory.env)
                self.python_env_create(bench_directory)

    def setup_nvm_and_yarn(self, bench_directory: BenchDirectory):
        try:
            output = self.host_run(
                ["source /scripts/helper-function.sh; env; setup_nvm_and_yarn $NVM_VERSION"],
                bench_directory,
                container=self.mode == "fm",
                capture_output=False,
            )
        except DockerException:
            pass

    def python_env_create(
        self, bench_directory: BenchDirectory, venv_path: str = "env", python_version: Optional[str] = None
    ):
        python_version = self.config.python_version if self.config.python_version else "3"

        venv_create_command = [f"python{python_version}", "-m", "venv", venv_path]

        self.printer.change_head(f"Creating python venv {'using uv' if self.config.uv else ''}")

        if self.config.uv:
            # First check if uv is already installed
            check_uv = None
            try:
                check_uv = self.host_run(
                    ["which", "uv"],
                    bench_directory,
                    container=self.mode == "fm",
                    capture_output=True,
                )
            except DockerException:
                pass

            # If which command returns nothing, uv is not installed
            if not check_uv or not check_uv.combined:
                output = self.host_run(
                    ["pip", "install", "uv"],
                    bench_directory,
                    container=self.mode == "fm",
                    capture_output=True,
                )

            venv_create_command = [
                "uv",
                "venv",
                "--no-cache-dir",
                "--seed",
                "--python",
                f"python{python_version}",
                venv_path,
            ]

        output = self.host_run(
            venv_create_command,
            bench_directory,
            # stream=False,
            container=self.mode == "fm",
            capture_output=True,
        )

        pkg_install = [f"{venv_path}/bin/python", "-m", "pip", "install", "wheel"]

        if self.config.uv:
            pkg_install = [
                "uv",
                "pip",
                "install",
                "--no-cache-dir",
                "--python",
                f"{venv_path}/bin/python",
                "-U",
                "wheel",
            ]

        output = self.host_run(
            pkg_install,
            bench_directory,
            # stream=False,
            container=self.mode == "fm",
            capture_output=True,
        )
        output = self.host_run(
            [f"{venv_path}/bin/python", "--version"],
            bench_directory,
            # stream=False,
            container=self.mode == "fm",
            capture_output=True,
        )
        self.printer.print(f"Created {output.combined[-1]} env {'using uv' if self.config.uv else ''}")

    def bench_install_all_apps_in_python_env(self, bench_directory: BenchDirectory):
        self.printer.change_head(f"Installing all apps in python env {'using uv' if self.config.uv else ''}")

        install_cmd = [self.bench_cli, "setup", "requirements", "--python"]

        if self.config.uv:
            install_cmd = [
                "uv",
                "pip",
                "install",
                "--no-cache-dir",
                "--python",
                "env/bin/python",
                "-U",
                # "--compile-bytecode"
                "-e",
            ]
            apps = [d for d in bench_directory.apps.iterdir() if d.is_dir()]
            for app in apps:
                self.host_run(
                    install_cmd + [f"apps/{app.name}"],
                    bench_directory,
                    # stream=False,
                    container=self.mode == "fm",
                    capture_output=False,
                )
        else:
            self.host_run(
                install_cmd,
                bench_directory,
                # stream=False,
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
            # stream=True,
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
        apps_txt_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure the directory exists

        with apps_txt_path.open("w") as f:
            for app_name in app_names:
                app_name = bench_directory.get_app_python_module_name(bench_directory.apps / app_name)
                f.write(f"{app_name}\n")
        self.printer.print("Configured apps.txt")

    def bench_build(self, bench_directory: BenchDirectory):
        # apps: list[Union[AppConfig, Path]] = self.apps

        apps = [d for d in bench_directory.apps.iterdir() if d.is_dir()]

        for app in apps:
            # Find corresponding AppConfig for the app to check for pre/post build commands
            app_config = None
            for config in self.apps:
                app_name = bench_directory.get_app_python_module_name(bench_directory.apps / config.dir_name)
                if app_name == app.name:
                    app_config = config
                    break

            # Define app directory path for container
            app_dir_path = f"/workspace/{bench_directory.path.name}/apps/{app.name}"

            # Run pre-build command if configured and in FM mode
            if self.mode == "fm" and app_config and app_config.fm_pre_build:
                self.printer.print(f"Running pre-build command for {app.name} in app directory")

                # Use _run_script method which handles script execution properly
                self._run_script(
                    app_config.fm_pre_build,
                    bench_directory,
                    f"pre-build script for {app.name}",
                    container=True,
                    app_name=app.name,
                    custom_workdir=app_dir_path,
                )

            # Run the regular build command
            # build_cmd = [
            #     self.bench_cli,
            #     "build",
            #     # "--app",
            #     # app.name,
            # ]

            prod_build_cmd = [
                self.bench_cli,
                "build",
                "--hard-link",
                "--production",
                "--force",
                # "--app",
                # app.name,
            ]

            # self.host_run(
            #     build_cmd,
            #     bench_directory,
            #     # stream=False,
            #     container=self.mode == "fm",
            #     capture_output=False,
            # )

            # print(f"removing {bench_directory.sites / 'assets'}")
            # shutil.rmtree(bench_directory.sites / 'assets')

            self.host_run(
                prod_build_cmd,
                bench_directory,
                # stream=False,
                container=self.mode == "fm",
                capture_output=False,
            )

        for app in apps:
            # Find corresponding AppConfig for the app to check for pre/post build commands
            app_config = None
            for config in self.apps:
                app_name = bench_directory.get_app_python_module_name(bench_directory.apps / config.dir_name)
                if app_name == app.name:
                    app_config = config
                    break

            # Define app directory path for container
            app_dir_path = f"/workspace/{bench_directory.path.name}/apps/{app.name}"

            # Run post-build command if configured and in FM mode
            if self.mode == "fm" and app_config and app_config.fm_post_build:
                self.printer.print(f"Running post-build command for {app.name} in app directory")

                # Use _run_script method which handles script execution properly
                self._run_script(
                    app_config.fm_post_build,
                    bench_directory,
                    f"post-build script for {app.name}",
                    container=True,
                    app_name=app.name,
                    custom_workdir=app_dir_path,
                )

            self.printer.print(f"Built app {app.name}")

        self.printer.print("Built all apps")

    def search_and_replace_in_database(
        self, search: str, replace: str, dry_run: bool = False, verbose: bool = False
    ) -> None:
        """
        Search and replace text across all text fields in the database.

        Args:
            search: Text to search for
            replace: Text to replace with
            dry_run: If True, only show what would be changed
            verbose: If True, show detailed output
        """
        try:
            # Copy search_replace.py to bench sites directory
            search_replace_script = Path(__file__).parent / "search_replace.py"
            if not search_replace_script.exists():
                self.printer.exit(f"Search/replace script not found at {search_replace_script}")

            bench_script_path = self.current.sites / "search_replace.py"
            shutil.copy2(search_replace_script, bench_script_path)

            try:
                # Build command for search/replace operation
                python_path = "../env/bin/python"
                search_replace_cmd = [python_path, "search_replace.py", self.site_name, search, replace]
                if dry_run:
                    search_replace_cmd.append("--dry-run")
                if verbose or self.config.verbose:
                    search_replace_cmd.append("--verbose")

                # Run the command using host_run and capture output
                result = self.host_run(
                    search_replace_cmd,
                    self.current,
                    container=self.mode == "fm",
                    capture_output=True,
                    workdir=f"/workspace/{self.current.path.name}/sites"
                    if self.mode == "fm"
                    else str(self.current.sites.absolute()),
                )

                # Print the output with proper formatting
                if result.combined:
                    for line in result.combined:
                        if line.strip():
                            self.printer.print(line.strip())

            finally:
                # Cleanup - remove the copied script
                if bench_script_path.exists():
                    bench_script_path.unlink()

        except Exception as e:
            self.printer.warning(f"Failed to perform search and replace: {str(e)}")

    def bench_symlink(self, bench_directory: BenchDirectory):
        self.printer.change_head("Symlinking")

        if self.bench_path.exists():
            self.bench_path.unlink()

        self.bench_path.symlink_to(get_relative_path(self.bench_path, bench_directory.path), True)

    # def bench_symlink_and_restart(self, bench_directory: BenchDirectory):
    #     self.printer.change_head("Symlinking")

    #     if self.bench_path.exists():
    #         self.bench_path.unlink()

    #     self.bench_path.symlink_to(get_relative_path(self.bench_path, bench_directory.path), True)

    #     start_time = time.time()

    #     if self.mode == "fm":
    #         restart_cmd = [self.fmx, "restart"]
    #         self.host_run(
    #             restart_cmd,
    #             bench_directory,
    #             container=True,
    #             capture_output=False,
    #         )
    #     else:
    #         services_to_restart = ["workers", "web"]
    #         for service in services_to_restart:
    #             command = ["sudo", "supervisorctl", "restart", f"frappe-bench-{service}:"]
    #             self.host_run(
    #                 command,
    #                 bench_directory,
    #                 # stream=False,
    #                 container=False,
    #                 capture_output=False,
    #             )

    #     self.printer.start("Working")
    #     self.printer.print("Symlinked and restarted")

    def bench_restart(
        self,
        bench_directory: BenchDirectory,
        migrate=False,
        migrate_timeout=1200,
        wait_workers=False,
        wait_workers_timeout=600,
        maintenance=False,
        maintenance_phases=["migrate", "start"],
    ):
        self.printer.change_head("Restart and Migrate")

        args = []

        if migrate:
            args += ["--migrate"]
            if migrate_timeout:
                args += ["--migrate-timeout", str(migrate_timeout)]

        if wait_workers:
            args += ["--wait-workers"]
            if wait_workers_timeout:
                args += ["--wait-workers-timeout", str(wait_workers_timeout)]

        if maintenance:
            args += ["--maintenance-mode"] + maintenance_phases

        # Run pre-scripts
        if self.config.host_pre_script:
            self._run_script(self.config.host_pre_script, bench_directory, "host pre-script")

        if self.mode == "fm" and self.config.fm_pre_script:
            self._run_script(self.config.fm_pre_script, bench_directory, "FM pre-script", container=True)

        start_time = time.time()

        if self.mode == "fm":
            restart_cmd = [self.fmx, "restart"] + args
            self.host_run(restart_cmd, bench_directory, container=True, capture_output=False, live_lines=50)
        else:
            services_to_restart = ["workers", "web"]
            for service in services_to_restart:
                command = ["sudo", "supervisorctl", "restart", f"frappe-bench-{service}:"]
                self.host_run(
                    command,
                    bench_directory,
                    # stream=False,
                    container=False,
                    capture_output=False,
                )

        if self.config.verbose:
            end_time = time.time()
            elapsed_time = end_time - start_time
            self.printer.print(
                f"Frappe Services Restart Time Taken: {human_readable_time(elapsed_time)}", emoji_code=":robot_face:"
            )
        self.printer.start("Working")
        self.printer.print("Symlinked and restarted")

        # Run post-scripts
        if self.mode == "fm" and self.config.fm_post_script:
            self._run_script(self.config.fm_post_script, bench_directory, "FM post-script", container=True)

        if self.config.host_post_script:
            self._run_script(self.config.host_post_script, bench_directory, "host post-script")

    def get_site_installed_apps(self, bench_directory: BenchDirectory):
        command = [self.bench_cli, "list-apps", "-f", "json"]
        try:
            output = self.host_run(
                command,
                bench_directory,
                # stream=False,
                container=self.mode == "fm",
                capture_output=True,
            )
        except DockerException:
            self.printer.warning(f"Not able to get current list of apps installed in {self.site_name}")
            return {self.site_name: []}
        return json.loads("".join(output.combined))

    def is_app_installed_in_site(self, site_name: str, app_name: str) -> bool:
        site_apps = self.site_installed_apps.get(site_name)

        if not site_apps:
            return False

        if app_name in site_apps:
            return True

        return False
