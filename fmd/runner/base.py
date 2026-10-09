import dataclasses
import functools
import importlib
import inspect
import os
import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Union

from fmd.redact import find_secret_values, redact, redact_command

_dock = None
try:
    _dock = importlib.import_module("frappe_manager.utils.docker")
except Exception:
    _dock = None

SubprocessOutput = getattr(_dock, "SubprocessOutput", None)
if SubprocessOutput is None:

    class SubprocessOutput:  # type: ignore
        pass


DockerException = getattr(_dock, "DockerException", None)

_DIM = "\033[2m"
_RESET = "\033[0m"


def redact_docker_exception(exc, secrets: Iterable[str] = ()):
    """Rebuild a DockerException with its command line and captured output redacted.

    Secret values found on the command line, plus any passed in, are masked verbatim, since a
    failing command can print them back in a format the pattern-based redaction does not know.
    """
    secrets = find_secret_values(exc.docker_command) | set(secrets)
    output = exc.output
    if dataclasses.is_dataclass(output):
        output = dataclasses.replace(
            output,
            stdout=[redact(line, secrets) for line in output.stdout],
            stderr=[redact(line, secrets) for line in output.stderr],
            combined=[redact(line, secrets) for line in output.combined],
        )
    return type(exc)(redact_command(exc.docker_command, secrets), output)


def redact_errors(method):
    """DockerException's message echoes the full command, including `--env KEY=VALUE` args."""
    signature = inspect.signature(method)

    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except Exception as e:
            if DockerException is None or not isinstance(e, DockerException):
                raise
            # Host commands get their env through the subprocess environment, not the command line
            env = signature.bind_partial(*args, **kwargs).arguments.get("env") or {}
            redacted = redact_docker_exception(e, find_secret_values([env, dict(os.environ)]))
        # Raised outside the except block so the unredacted original is not chained as __context__
        raise redacted from None

    return wrapper


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
            logger.debug(f"COMMAND [{mode}]: {' '.join(redact_command(command))}")
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
        command_str = " ".join(redact_command(command))
        print(f"{_DIM}$ [{mode}] {command_str}  ({elapsed:.2f}s){_RESET}")
        try:
            from fmd.logger import get_logger

            logger = get_logger()
            logger.debug(f"TIMING: {elapsed:.2f}s for command: {command_str}")
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
