import gzip
import shutil
import time
import os
import sys
import concurrent.futures
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
    update_json_keys_in_file_path,
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
        # Adjust bench_path based on output_dir
        self.bench_path = config.bench_path
        self.path = self.bench_path

        self.output_dir = self.bench_path.parent

        self.mode = "fm"
        self.config = config
        self.verbose = config.verbose
        self.apps = config.apps
        self.printer = richprint
        self.bench_cli = "/usr/local/bin/bench"
        self.current = BenchDirectory(self.bench_path)

        self.printer.start("Working")

    def build_images(self, force: bool = False, image_type: str = "all"):
        """Builds specified images (Frappe, Nginx, or all)."""

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Build the Frappe base image if we are building any image that depends on it.
        if image_type in ("all", "frappe", "nginx") and self.config.build_frappe:
            self._build_frappe_base_image(force)

        # Bake the bench if not already baked. This is needed for both frappe and nginx final images.
        if image_type in ("all", "frappe", "nginx"):
            if not self.is_baked(self.current):
                self.printer.change_head("Baking bench...")
                self.bake()
                self.printer.print("Bench baked successfully.")
            else:
                self.printer.print("Bench already baked. Skipping bake process.")

        # Build the final images.
        if image_type in ("all", "frappe") and self.config.build_frappe:
            self._build_frappe_image(force)

        if image_type in ("all", "nginx") and self.config.build_nginx:
            self._build_nginx_image(force)

    def _build_frappe_base_image(self, force: bool = False):
        """Builds the Frappe base image (builder stage)."""
        build_config = self.config.build_frappe
        self.printer.change_head("Rendering Frappe Dockerfile")
        rendered_dockerfile_path = self.output_dir / "Dockerfile.fmd.frappe"

        build_config.render_dockerfile(rendered_dockerfile_path, site_name=self.config.site_name, bench_name=self.bench_path.name)
        self.printer.print(f"Frappe Dockerfile rendered at {rendered_dockerfile_path}")

        builder_image_name = build_config.builder_image_name
        
        self.printer.change_head(f"Preparing base image {builder_image_name}")
        self.printer.print(f"Building base image {builder_image_name}...")
        build_cmd = [
            "docker",
            "build",
            "-t",
            builder_image_name,
            "--target",
            "builder",
            "-f",
            str(rendered_dockerfile_path),
        ]

        if build_config.platforms:
            build_cmd.extend(["--platform", ",".join(build_config.platforms)])

        if build_config.build_args:
            for arg in build_config.build_args:
                if arg:
                    build_cmd.extend(["--build-arg", arg])

        build_cmd.append(str(self.output_dir))

        output_stream = run_command_with_exit_code(build_cmd, stream=True)
        self.printer.live_lines(output_stream, lines=10)
        self.printer.print(f"Base image '{builder_image_name}' built successfully.")

    def _build_frappe_image(self, force: bool = False):
        """Builds the final Frappe image from the baked bench."""

        build_config = self.config.build_frappe
        rendered_dockerfile_path = self.output_dir / "Dockerfile.fmd.frappe"

        # Build final image
        final_image_name = build_config.image
        self.printer.change_head(f"Building final image: {final_image_name}")
        bench_dir_name = self.bench_path.name
        final_build_cmd = [
            "docker",
            "build",
            "-t",
            final_image_name,
            "-f",
            str(rendered_dockerfile_path),
            "--build-arg",
            f"BENCH={bench_dir_name}",
        ]

        if build_config.platforms:
            final_build_cmd.extend(["--platform", ",".join(build_config.platforms)])

        if build_config.build_args:
            for arg in build_config.build_args:
                if arg:
                    final_build_cmd.extend(["--build-arg", arg])

        final_build_cmd.append(str(self.output_dir))  # Changed context

        output_stream = run_command_with_exit_code(final_build_cmd, stream=True)
        self.printer.live_lines(output_stream, lines=10)
        self.printer.print(f"Final image '{final_image_name}' built successfully.")


    def _build_nginx_image(self, force: bool = False):
        """Builds the Nginx image."""

        build_config = self.config.build_nginx
        self.printer.change_head("Rendering Nginx Dockerfile")
        rendered_dockerfile_path = self.output_dir / "Dockerfile.fmd.nginx"

        build_config.render_dockerfile(rendered_dockerfile_path, site_name=self.config.site_name, bench_name=self.bench_path.name)

        self.printer.print(f"Nginx Dockerfile rendered at {rendered_dockerfile_path}")
        image_name = build_config.image
        self.printer.change_head(f"Preparing Nginx image: {image_name}")

        self.printer.print(f"Building Nginx image '{image_name}'...")
        build_cmd = ["docker", "build", "-t", image_name, "-f", str(rendered_dockerfile_path)]

        if build_config.platforms:
            build_cmd.extend(["--platform", ",".join(build_config.platforms)])

        build_cmd.append(str(self.output_dir))  # Changed context
        output_stream = run_command_with_exit_code(build_cmd, stream=True)
        self.printer.live_lines(output_stream, lines=10)
        self.printer.print(f"Nginx image '{image_name}' built successfully.")


    def bake(self):
        self.printer.print(f"Bench: {self.config.bench_name}")
        self.current.setup_dir(create_tmps=True)
        self.printer.change_head("Configuring bench dirs")
        self.config.to_toml(self.current.path / "fmd-config.toml")
        self.clone_apps(self.current)
        self.chown_dir(self.current, '/workspace/frappe-bench', f'frappe:{os.getgid()}')
        self.python_env_create(self.current)
        self.bench_setup_requiments(self.current)
        self.sync_configs_with_files(self.current)
        self.bench_build(self.current)

    def is_baked(self, bench_directory: BenchDirectory) -> bool:
        """
        Checks if the bench is considered 'baked'.
        A bench is considered baked if:
        1. The 'sites/assets' directory exists and contains files.
        2. All apps listed in 'sites/apps.txt' have their corresponding directories in 'apps/'.
        """
        assets_path = bench_directory.sites / "assets"
        if not (assets_path.is_dir() and any(assets_path.iterdir())):
            return False

        apps_txt_path = bench_directory.sites / "apps.txt"
        if not apps_txt_path.is_file():
            self.printer.print(f"Warning: {apps_txt_path} not found. Cannot verify all apps are present.", emoji_code=":warning:")
            return False

        with apps_txt_path.open("r") as f:
            installed_apps = [line.strip() for line in f if line.strip()]

        for app_name in installed_apps:
            app_path = bench_directory.apps / app_name
            if not app_path.is_dir():
                self.printer.print(f"App '{app_name}' listed in apps.txt not found at {app_path}", emoji_code=":x:")
                return False

        return True

    def extract_timestamp(self, dir_name: str) -> int:
        try:
            timestamp_str = dir_name.split("_")[-1]
            return int(timestamp_str)
        except ValueError:
            return 0

    def _clone_task_wrapper(self, clone_func, **kwargs):
        app = kwargs['app']
        self.printer.print(f"Cloning {app.repo}...")
        try:
            result = clone_func(**kwargs)
            self.printer.print(f"Finished cloning {app.repo}.")
            return result
        except Exception as e:
            self.printer.error(f"Failed to clone {app.repo}: {e}")
            raise

    def chown_dir(self, bench_directory: BenchDirectory, target_path: str, user: str = "frappe:frappe"):
        """
        Changes the ownership of a directory, intended for volume mounted directories inside a container.
        Args:
            bench_directory: The BenchDirectory context.
            target_path: The path to the directory inside the container.
            user: The user and group to set, e.g., '1000:1000'.
        """
        self.printer.change_head(f"Changing ownership of {target_path} to {user}")
        command = ["chown", "-R", user, target_path]
        self.host_run(
            command,
            bench_directory,
            container=True,
            container_user="root",
            capture_output=False,
        )
        command = ["chmod", "-R", 'g+rwx', target_path]
        self.host_run(
            command,
            bench_directory,
            container=True,
            container_user="root",
            capture_output=False,
        )
        self.printer.print(f"Ownership of {target_path} changed to {user}")

    

    def clone_apps(
        self,
        bench_directory: "BenchDirectory",
        data_directory: Optional["BenchDirectory"] = None,
        overwrite: bool = False,
        backup=True,
    ):
        clone_tasks = []
        clone_map = {}  # (repo, ref) -> clone_path
        app_clone_info = [] # list of (app, clone_path)

        # 1. Prepare clone tasks
        self.printer.change_head("Preparing to clone repositories")
        for app in self.apps:
            clone_path = None
            if app.symlink:
                key = (app.repo, app.ref)
                if key in clone_map:
                    clone_path = clone_map[key]
                    self.printer.print(f"Will reuse clone for {app.repo}@{app.ref} subdir: {app.subdir_path}")
                else:
                    if not data_directory:
                        raise RuntimeError("Deployment data directory is not provided")
                    clone_path = data_directory.get_frappe_bench_app_path(
                        app, append_release_name=bench_directory.path.resolve().name, suffix="_clone"
                    )
                    clone_map[key] = clone_path
                    clone_tasks.append((data_directory.clone_app, {'app': app, 'clone_path': clone_path, 'move_to_subdir': False}))
            else:
                clone_path = bench_directory.get_frappe_bench_app_path(app, suffix="_clone")
                clone_tasks.append((bench_directory.clone_app, {'app': app, 'clone_path': clone_path}))

            app_clone_info.append((app, clone_path))
        self.printer.print(f"Found {len(clone_tasks)} unique repositories to clone.")

        # 2. Execute clone tasks in parallel
        self.printer.change_head(f"Cloning {len(clone_tasks)} repositories")
        with concurrent.futures.ThreadPoolExecutor() as executor:

            future_to_app = {
                executor.submit(self._clone_task_wrapper, func, **kwargs): kwargs['app']
                for func, kwargs in clone_tasks
            }
            for future in concurrent.futures.as_completed(future_to_app):
                app = future_to_app[future]
                try:
                    future.result()
                except Exception:
                    # The exception is already printed by the wrapper.
                    # Re-raise to stop the process.
                    raise

        self.printer.print("All repositories cloned successfully.")

        # 3. Process apps after cloning
        for app, clone_path in app_clone_info:
            self.printer.change_head(f"Processing app {app.repo}")
            from_dir = clone_path

            if app.symlink:
                if app.subdir_path:
                    from_dir = from_dir / app.subdir_path

            app_name = app.app_name if app.app_name else bench_directory.get_app_python_module_name(from_dir)
            to_dir = bench_directory.apps / app_name

            import datetime
            if to_dir.exists():
                if not overwrite:
                    raise FileExistsError(f"App directory '{to_dir}' already exists. Use \"--overwrite\" to overwrite it.")

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

            self.printer.print(f"{'Remote removed ' if app.remove_remote else ''}Cloned Repo: {app.repo}, Module Name: '{app_name}'")

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
        container_user: Optional[str] = None,
        capture_output: bool = True,
        live_lines: int = 4,
        workdir: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
    ) -> Union[Iterable[Tuple[str, bytes]], SubprocessOutput]:
        if self.verbose:
            start_time = time.time()

        base_env = {"COREPACK_ENABLE_DOWNLOAD_PROMPT": "0"}

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

        if self.config.build_frappe:
            workdir = "/workspace/frappe-bench"

        compose_file: ComposeFile = ComposeFile(self.path.parent / "docker-compose.yml")
        compose_project: ComposeProject = ComposeProject(compose_file_manager=compose_file)

        user_to_run_as = container_user
        if user_to_run_as is None:
            # if self.config.build_frappe:
            #     user_to_run_as = f"{os.getuid()}:{os.getgid()}"
            # else:
            user_to_run_as = "frappe"

        if capture_output:
            if self.config.build_frappe:
                output = DockerClient().run(
                    image=self.config.build_frappe.builder_image_name,
                    user=user_to_run_as,
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
                    user=user_to_run_as,
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
            if self.config.build_frappe:
                output = DockerClient().run(
                    image=self.config.build_frappe.builder_image_name,
                    user=user_to_run_as,
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
                    user=user_to_run_as,
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

        prod_build_cmd = [
            self.bench_cli,
            "build",
            # "--production",
            "--force",
            "--hard-link",
        ]

        self.host_run(
            prod_build_cmd[:-1],
            bench_directory,
            container=self.mode == "fm",
            capture_output=False,
        )

        self.host_run(
            prod_build_cmd,
            bench_directory,
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

            # self.printer.print(f"Built app {app.name}")

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

    def sync_configs_with_files(self, bench_directory: BenchDirectory):
        self.printer.change_head("Updating common_site_config.json")
        common_site_config_path = bench_directory.sites / "common_site_config.json"

        if self.config.common_site_config:
            update_json_keys_in_file_path(common_site_config_path, self.config.common_site_config)

        self.printer.print("Updated common_site_config.json")
