import importlib
import os
import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Union

_dock = None
try:
    _dock = importlib.import_module("frappe_manager.utils.docker")
except Exception:
    _dock = None

SubprocessOutput = getattr(_dock, "SubprocessOutput", None)
if SubprocessOutput is None:

    class SubprocessOutput:  # type: ignore
        pass


def is_ci() -> bool:
    return os.environ.get("CI", "").lower() == "true"


def is_tty() -> bool:
    return sys.stdout.isatty()


class CommandRunner(ABC):
    def __init__(self, verbose: bool, printer) -> None:
        self.verbose = verbose
        self.printer = printer

    def _log_timing(self, start_time: Optional[float], command: list) -> None:
        if self.verbose and start_time is not None:
            elapsed = time.time() - start_time
            self.printer.print(
                f"Time Taken: {elapsed:.2f} sec, Command: '{' '.join(command)}'",
                emoji_code=":robot_face:",
            )

    @property
    def supports_db_restore(self) -> bool:
        return True

    @abstractmethod
    def run(
        self,
        command: list[str],
        bench_directory,
        capture_output: bool = True,
        live_lines: int = 4,
        workdir: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
    ) -> Union[Iterable[Tuple[str, bytes]], SubprocessOutput, None]: ...

    @abstractmethod
    def restart_services(self, args: List[str], bench_directory) -> None: ...

    @abstractmethod
    def venv_paths(self, deploy_path: Path) -> tuple[Path, Path]: ...

    @abstractmethod
    def workdir_for_bench(self, bench_directory) -> str: ...

    @abstractmethod
    def workdir_for_sites(self, bench_directory) -> str: ...

    @abstractmethod
    def app_exec_path(self, bench_directory, app_name: str) -> str: ...

    @abstractmethod
    def backup_path(self, host_backup_dir: Path, file_name: str) -> str: ...
