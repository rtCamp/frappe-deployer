import importlib
import os
import shlex
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
        platform: Optional[str] = None,
    ) -> None:
        super().__init__(verbose, printer)
        self.mode = mode
        self.config = config
        self.docker_host = docker_host
        self.platform = platform

    def _resolve_image(self) -> str:
        if self.config.release.runner_image:
            return self.config.release.runner_image
        return self._detect_image()

    def _detect_image(self) -> str:
        import importlib.metadata

        version = importlib.metadata.version("frappe-manager")
        return f"ghcr.io/rtcamp/frappe-manager-frappe:v{version}"

    def _compose_project_dir(self) -> Path:
        return self.config.workspace_root

    @property
    def supports_db_restore(self) -> bool:
        return self.mode == "exec"

    def venv_paths(self, deploy_path: Path) -> tuple[Path, Path]:
        host = deploy_path / ".cache" / "frappe-deployer-venv"
        exec_path = Path("/workspace/.cache/frappe-deployer-venv")
        return host, exec_path

    def _host_to_container(self, host_path: Path) -> str:
        workspace_mount = self.config.workspace_root / "workspace"
        try:
            relative = host_path.relative_to(workspace_mount)
            return f"/workspace/{relative}"
        except ValueError:
            return "/workspace/frappe-bench"

    def workdir_for_bench(self, bench_directory) -> str:
        if self.mode == "image":
            return "/workspace/frappe-bench"
        return self._host_to_container(bench_directory.path)

    def workdir_for_sites(self, bench_directory) -> str:
        return self._host_to_container(bench_directory.sites)

    def app_exec_path(self, bench_directory, app_name: str) -> str:
        return self._host_to_container(bench_directory.apps / app_name)

    def backup_path(self, host_backup_dir: Path, file_name: str) -> str:
        return f"/workspace/{'/'.join(host_backup_dir.parts[-2:])}/{file_name}"

    def restart_services(self, args: List[str], bench_directory) -> None:
        self.run(
            ["fmx", "restart"] + args,
            bench_directory,
            capture_output=False,
            live_lines=50,
            workdir="/workspace",
            tag_streams=True,
        )

    def run(
        self,
        command: list[str],
        bench_directory,
        capture_output: bool = True,
        live_lines: int = 4,
        workdir: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        tag_streams: bool = False,
    ) -> Union[Iterable[Tuple[str, bytes]], SubprocessOutput, None]:
        start_time = time.time()

        self._log_command(command, mode=self.mode)

        if self.mode == "image":
            result = self._run_in_image(command, bench_directory, capture_output, live_lines, workdir, env, tag_streams)
        else:
            result = self._run_in_exec(command, bench_directory, capture_output, live_lines, workdir, env, tag_streams)

        self._log_timing(start_time, command, mode=self.mode)
        return result

    @staticmethod
    def _tag_stderr_stream(stream: Iterable) -> Iterable:
        ANSI_DIM = "\033[2m"
        ANSI_RESET = "\033[0m"
        for source, line in stream:
            if source == "stderr":
                if isinstance(line, bytes):
                    line = ANSI_DIM.encode() + line + ANSI_RESET.encode()
                else:
                    line = f"{ANSI_DIM}{line}{ANSI_RESET}"
            yield source, line

    def _run_in_image(self, command, bench_directory, capture_output, live_lines, workdir, env, tag_streams=False):
        _DockerClient = None
        try:
            _dc = importlib.import_module("frappe_manager.docker.docker_client")
            _DockerClient = getattr(_dc, "DockerClient", None)
        except Exception:
            pass

        if _DockerClient is None:
            raise RuntimeError("frappe_manager.docker.docker_client.DockerClient unavailable")

        base_env = {
            "HOME": "/workspace",
            "USER": "frappe",
            "GROUP": "frappe",
            "PATH": "/workspace/frappe-bench/.uv/python-default/bin:/workspace/frappe-bench/.fnm/aliases/default/bin:/usr/local/bin:/opt/user/.bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin",
            "FNM_DIR": "/workspace/frappe-bench/.fnm",
            "FNM_MULTISHELL_PATH": "/workspace/frappe-bench/.fnm",
            "FNM_COREPACK_ENABLED": "true",
            "COREPACK_HOME": "/workspace/frappe-bench/.fnm/corepack",
            "COREPACK_ENABLE_DOWNLOAD_PROMPT": "0",
            "UV_PYTHON_INSTALL_DIR": "/workspace/frappe-bench/.uv/python",
            "UV_CACHE_DIR": "/workspace/frappe-bench/.uv/cache",
            "UV_PYTHON_DOWNLOADS": "automatic",
            "UV_PYTHON_PREFERENCE": "only-managed",
            "BENCH_USE_UV": "true",
            "PYTHONUNBUFFERED": "1",
            "LC_ALL": "en_US.UTF-8",
            "LANG": "en_US.UTF-8",
            "LANGUAGE": "en_US.UTF-8",
        }
        for _k in ("DOCKER_HOST", "GITHUB_TOKEN", "GIT_TOKEN", "UV_LINK_MODE", "DOCKER_DEFAULT_PLATFORM"):
            if _k in os.environ:
                base_env[_k] = os.environ[_k]
        if env:
            base_env.update(env)
        if self.docker_host:
            base_env["DOCKER_HOST"] = self.docker_host

        docker_command = shlex.join(command)
        docker_command = f"-c 'umask 000; source /etc/bash.bashrc; {docker_command}'"

        effective_workdir = workdir or "/workspace/frappe-bench"
        image = self._resolve_image()

        volumes = [f"{bench_directory.path.absolute()}:/workspace/frappe-bench"]

        output = _DockerClient().run(
            image=image,
            user="frappe",
            command=docker_command,
            workdir=effective_workdir,
            env=base_env,
            entrypoint="/bin/bash",
            platform=self.platform or None,
            pull="missing",
            volume=volumes,
            stream=not capture_output,
            rm=True,
        )

        if capture_output:
            self._log_output(output)
            return output

        stream = self._tag_stderr_stream(output) if tag_streams else output
        self.printer.live_lines(stream, lines=live_lines)
        return None

    def _run_in_exec(self, command, bench_directory, capture_output, live_lines, workdir, env, tag_streams=False):
        from frappe_manager.docker.docker_compose import DockerComposeWrapper

        compose_file = self._compose_project_dir() / "docker-compose.yml"
        compose = DockerComposeWrapper(compose_file)

        effective_workdir = workdir or self.workdir_for_bench(bench_directory)
        bench_container_path = self.workdir_for_bench(bench_directory)

        uv_env = {
            "UV_PYTHON_INSTALL_DIR": f"{bench_container_path}/.uv/python",
            "UV_CACHE_DIR": f"{bench_container_path}/.uv/cache",
        }
        if env:
            uv_env.update(env)

        full_bash_cmd = f"source /etc/bash.bashrc; {shlex.join(command)}"
        command_str = f"/bin/bash -c {shlex.quote(full_bash_cmd)}"

        env_list = [f"{k}={v}" for k, v in uv_env.items()]

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
            self._log_output(output)
            return output

        stream = self._tag_stderr_stream(output) if tag_streams else output
        self.printer.live_lines(stream, lines=live_lines)
        return None
