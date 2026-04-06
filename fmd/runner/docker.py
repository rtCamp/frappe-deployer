import importlib
import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import Iterable, List, Literal, Optional, Tuple, Union

from fmd.runner.base import CommandRunner, SubprocessOutput

_dock = None
try:
    _dock = importlib.import_module("frappe_manager.utils.docker")
except Exception:
    _dock = None

run_command_with_exit_code = getattr(_dock, "run_command_with_exit_code", None)

if run_command_with_exit_code is None:

    def run_command_with_exit_code(*args, **kwargs):
        raise RuntimeError("run_command_with_exit_code unavailable in this environment")


def _run_cmd(*args, **kwargs):
    if callable(run_command_with_exit_code):
        return run_command_with_exit_code(*args, **kwargs)
    raise RuntimeError("run_command_with_exit_code unavailable in this environment")


class DockerRunner(CommandRunner):
    def __init__(
        self,
        mode: Literal["image", "exec"],
        config,
        verbose: bool,
        printer,
        docker_host: Optional[str] = None,
    ) -> None:
        super().__init__(verbose, printer)
        self.mode = mode
        self.config = config
        self.docker_host = docker_host

    def _resolve_image(self) -> str:
        if self.config.bake and self.config.bake.builder_image:
            return self.config.bake.builder_image
        return self._detect_image()

    def _detect_image(self) -> str:
        env = os.environ.copy()
        if self.docker_host:
            env["DOCKER_HOST"] = self.docker_host

        compose_project = self.config.site_name.replace(".", "").replace("-", "")

        cmd = [
            "docker",
            "ps",
            "--filter",
            f"label=com.docker.compose.service=frappe",
            "--filter",
            f"label=com.docker.compose.project={compose_project}",
            "--format",
            "{{.Image}}",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        image = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
        if not image:
            raise RuntimeError(
                f"Could not auto-detect Docker image for site '{self.config.site_name}'. "
                "Set bake.builder_image in config to override."
            )
        return image

    def _compose_project_dir(self) -> Path:
        return self.config.deploy_dir_path

    @property
    def supports_db_restore(self) -> bool:
        return self.mode == "exec"

    def venv_paths(self, deploy_path: Path) -> tuple[Path, Path]:
        host = deploy_path / ".cache" / "frappe-deployer-venv"
        exec_path = Path("/workspace/.cache/frappe-deployer-venv")
        return host, exec_path

    def workdir_for_bench(self, bench_directory) -> str:
        return "/workspace/frappe-bench"

    def workdir_for_sites(self, bench_directory) -> str:
        return "/workspace/frappe-bench/sites"

    def app_exec_path(self, bench_directory, app_name: str) -> str:
        return f"/workspace/frappe-bench/apps/{app_name}"

    def backup_path(self, host_backup_dir: Path, file_name: str) -> str:
        return f"/workspace/{'/'.join(host_backup_dir.parts[-2:])}/{file_name}"

    def restart_services(self, args: List[str], bench_directory) -> None:
        if self.mode == "exec":
            from frappe_manager.docker.docker_compose import DockerComposeWrapper

            compose_file = self._compose_project_dir() / "docker-compose.yml"
            compose = DockerComposeWrapper(compose_file)

            old_docker_host = None
            if self.docker_host:
                old_docker_host = os.environ.get("DOCKER_HOST")
                os.environ["DOCKER_HOST"] = self.docker_host

            try:
                output = compose.restart(services=["frappe"], stream=True)
                self.printer.live_lines(output, lines=50)
            finally:
                if self.docker_host:
                    if old_docker_host is None:
                        os.environ.pop("DOCKER_HOST", None)
                    else:
                        os.environ["DOCKER_HOST"] = old_docker_host
        else:
            self.run(
                ["fmx", "restart"] + args, bench_directory, capture_output=False, live_lines=50, workdir="/workspace"
            )

    def run(
        self,
        command: list[str],
        bench_directory,
        capture_output: bool = True,
        live_lines: int = 4,
        workdir: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
    ) -> Union[Iterable[Tuple[str, bytes]], SubprocessOutput, None]:
        start_time = time.time() if self.verbose else None

        if self.mode == "image":
            result = self._run_in_image(command, bench_directory, capture_output, live_lines, workdir, env)
        else:
            result = self._run_in_exec(command, bench_directory, capture_output, live_lines, workdir, env)

        self._log_timing(start_time, command)
        return result

    def _run_in_image(self, command, bench_directory, capture_output, live_lines, workdir, env):
        _DockerClient = None
        try:
            _dc = importlib.import_module("frappe_manager.docker.docker_client")
            _DockerClient = getattr(_dc, "DockerClient", None)
        except Exception:
            pass

        if _DockerClient is None:
            raise RuntimeError("frappe_manager.docker.docker_client.DockerClient unavailable")

        base_env = os.environ.copy()
        base_env["COREPACK_ENABLE_DOWNLOAD_PROMPT"] = "0"
        if env:
            base_env.update(env)
        if self.docker_host:
            base_env["DOCKER_HOST"] = self.docker_host

        docker_command = " ".join(command)
        docker_command = f"-c 'source /etc/bash.bashrc; {docker_command}'"

        effective_workdir = workdir or "/workspace/frappe-bench"
        image = self._resolve_image()

        output = _DockerClient().run(
            image=image,
            user="frappe",
            command=docker_command,
            workdir=effective_workdir,
            env=base_env,
            entrypoint="/bin/bash",
            pull="missing",
            volume=[f"{bench_directory.path}:/workspace/frappe-bench"],
            stream=not capture_output,
            rm=True,
        )

        if capture_output:
            return output

        self.printer.live_lines(output, lines=live_lines)
        return None

    def _run_in_exec(self, command, bench_directory, capture_output, live_lines, workdir, env):
        from frappe_manager.docker.docker_compose import DockerComposeWrapper

        compose_file = self._compose_project_dir() / "docker-compose.yml"
        compose = DockerComposeWrapper(compose_file)

        effective_workdir = workdir or "/workspace/frappe-bench"
        full_bash_cmd = f"source /etc/bash.bashrc; {' '.join(command)}"
        command_str = f"/bin/bash -c {shlex.quote(full_bash_cmd)}"

        env_list = [f"{k}={v}" for k, v in env.items()] if env else None

        old_docker_host = None
        if self.docker_host:
            old_docker_host = os.environ.get("DOCKER_HOST")
            os.environ["DOCKER_HOST"] = self.docker_host

        try:
            output = compose.exec(
                service="frappe",
                command=command_str,
                user="frappe",
                workdir=effective_workdir,
                env=env_list,
                no_tty=True,
                stream=not capture_output,
            )
        finally:
            if self.docker_host:
                if old_docker_host is None:
                    os.environ.pop("DOCKER_HOST", None)
                else:
                    os.environ["DOCKER_HOST"] = old_docker_host

        if capture_output:
            return output

        self.printer.live_lines(output, lines=live_lines)
        return None
