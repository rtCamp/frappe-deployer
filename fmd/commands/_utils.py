from pathlib import Path
from typing import Any, Optional
import subprocess
import sys

try:
    import typer
except Exception:
    typer = None

from fmd.config.config import Config
from fmd.exceptions import ConfigPathDoesntExist
from fmd.runner.docker import DockerRunner
from fmd.runner.host import HostRunner

try:
    from frappe_manager.output_manager import RichOutputHandler
    from fmd.logger import get_logger
    from fmd.logger.logging_output import LoggingOutputHandler

    _base_printer = RichOutputHandler()

    # Only log to file, not console (console would clutter output)
    _logger = get_logger(console_level=None, file_level="DEBUG")

    _logger.info("")
    _logger.info(f"{'=' * 20} FMD Invoked {'=' * 20}")
    _logger.info(f"COMMAND: {' '.join(sys.argv)}")
    _logger.info(f"CWD: {Path.cwd()}")
    _logger.info("=" * 60)
    _logger.info("")

    _printer = LoggingOutputHandler(_base_printer, _logger)
except Exception:

    class _PrinterStub:
        def print(self, *a, **kw):
            print(*a)

        def change_head(self, *a, **kw):
            print(*a)

        def error(self, *a, **kw):
            print(*a)

        def warning(self, *a, **kw):
            print(*a)

        def live_lines(self, data, **kw):
            for source, line in data:
                if isinstance(line, bytes):
                    line = line.decode(errors="replace")
                print(line.rstrip())

        def start(self, *a, **kw):
            pass

        def stop(self, *a, **kw):
            pass

    _printer = _PrinterStub()

_verbose: Optional[bool] = None


def set_verbose(v: bool) -> None:
    global _verbose
    _verbose = v


def parse_app_option(app_strings: list[str]) -> list[dict]:
    result = []
    for s in app_strings:
        parts = s.split(":")
        app: dict[str, Any] = {"repo": parts[0]}
        if len(parts) > 1 and parts[1]:
            app["ref"] = parts[1]
        if len(parts) > 2 and parts[2]:
            app["subdir_path"] = parts[2]
        result.append(app)
    return result


def load_config(
    config_path: Optional[Path] = None,
    overrides: Optional[dict] = None,
    create_if_missing: bool = False,
) -> Config:
    effective: dict = dict(overrides) if overrides else {}
    if _verbose is not None and "verbose" not in effective:
        effective["verbose"] = _verbose
    overrides = effective or None

    if config_path is None:
        if not overrides or "site_name" not in overrides:
            raise ValueError("bench_name argument or --config/-c is required.")
        return Config.from_toml(overrides=overrides)

    if not config_path.exists():
        if create_if_missing and overrides and "site_name" in overrides:
            config = Config.from_toml(overrides=overrides)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config.to_toml(config_path)
            return config
        raise ConfigPathDoesntExist(str(config_path))
    return Config.from_toml(config_file_path=config_path, overrides=overrides or None)


def build_runners(config: Config):
    platform = config.release.platform if config.release.platform else None
    image_runner = DockerRunner(
        mode="image", config=config, verbose=config.verbose, printer=_printer, platform=platform
    )
    exec_runner = DockerRunner(mode="exec", config=config, verbose=config.verbose, printer=_printer)
    host_runner = HostRunner(verbose=config.verbose, printer=_printer)
    return image_runner, exec_runner, host_runner


def get_printer():
    return _printer


def is_exec_mode_available(workspace_root: Path) -> bool:
    compose_file = workspace_root / "docker-compose.yml"

    if not compose_file.exists():
        return False

    try:
        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "ps", "--services", "--filter", "status=running"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return False

        services = result.stdout.strip().split("\n")
        return "frappe" in [s for s in services if s]
    except Exception:
        return False
