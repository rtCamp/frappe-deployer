import importlib
import os
import time
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Union

from fmd.runner.base import CommandRunner, SubprocessOutput, is_ci, is_tty

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


class HostRunner(CommandRunner):
    def __init__(self, verbose: bool, printer) -> None:
        super().__init__(verbose, printer)

    @property
    def supports_db_restore(self) -> bool:
        return False

    def venv_paths(self, deploy_path: Path) -> tuple[Path, Path]:
        host = Path.home() / ".cache" / "frappe-deployer-venv"
        return host, host

    def workdir_for_bench(self, bench_directory) -> str:
        return str(bench_directory.path.absolute())

    def workdir_for_sites(self, bench_directory) -> str:
        return str(bench_directory.sites.absolute())

    def app_exec_path(self, bench_directory, app_name: str) -> str:
        return str(bench_directory.apps / app_name)

    def backup_path(self, host_backup_dir: Path, file_name: str) -> str:
        return str((host_backup_dir / file_name).absolute())

    def restart_services(self, args: List[str], bench_directory) -> None:
        raise NotImplementedError("HostRunner does not support restart_services - use FM or direct bench commands")

    def run_cmd(
        self,
        command: list[str],
        cwd: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
    ) -> SubprocessOutput:
        start_time = time.time()
        self._log_command(command, mode="host")

        base_env = os.environ.copy()
        if env:
            base_env.update(env)

        output = _run_cmd(
            command,
            stream=False,
            capture_output=True,
            cwd=cwd,
            env=base_env,
        )

        self._log_output(output)
        self._log_timing(start_time, command, mode="host")
        return output

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

        self._log_command(command, mode="host")

        base_env = os.environ.copy()
        if env:
            base_env.update(env)

        output = _run_cmd(
            command,
            stream=not capture_output,
            capture_output=capture_output,
            cwd=workdir or str(bench_directory.path.absolute()),
            env=base_env,
        )

        if capture_output:
            self._log_output(output)
            self._log_timing(start_time, command, mode="host")
            return output

        if not is_ci() and is_tty():
            self.printer.live_lines(output, lines=live_lines)
        else:
            for source, line in output:
                if isinstance(line, bytes):
                    line = line.decode(errors="replace")
                self.printer.print(line.rstrip(), emoji_code="")

        self._log_timing(start_time, command, mode="host")
        return None
