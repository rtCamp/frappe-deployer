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


_DIM = "\033[2m"
_RESET = "\033[0m"


def is_ci() -> bool:
    return os.environ.get("CI", "").lower() == "true"


def is_tty() -> bool:
    return sys.stdout.isatty()


class CommandRunner(ABC):
    def __init__(self, verbose: bool, printer) -> None:
        self.verbose = verbose
        self.printer = printer

    def _log_command(self, command: list[str], mode: str = "exec") -> None:
        try:
            from fmd.logger import get_logger

            logger = get_logger()
            logger.debug(f"COMMAND [{mode}]: {' '.join(command)}")
        except Exception:
            pass

    def _log_output(self, output) -> None:
        try:
            from fmd.logger import get_logger

            logger = get_logger()
            lines = getattr(output, "combined", None) or getattr(output, "stdout", None) or []
            for line in lines:
                if isinstance(line, bytes):
                    line = line.decode(errors="replace")
                line = line.rstrip()
                if line:
                    logger.debug(f"OUTPUT: {line}")
        except Exception:
            pass

    def _log_timing(self, start_time: Optional[float], command: list, mode: str = "exec") -> None:
        if start_time is None:
            return
        elapsed = time.time() - start_time
        print(f"{_DIM}$ [{mode}] {' '.join(command)}  ({elapsed:.2f}s){_RESET}")
        try:
            from fmd.logger import get_logger

            logger = get_logger()
            logger.debug(f"TIMING: {elapsed:.2f}s for command: {' '.join(command)}")
        except Exception:
            pass

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
        tag_streams: bool = False,
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
