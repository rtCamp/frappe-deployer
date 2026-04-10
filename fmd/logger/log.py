import gzip
import logging
import logging.handlers
import os
import re
import shutil
from pathlib import Path

from rich.logging import RichHandler

CLI_LOG_DIRECTORY = Path.home() / ".fmd" / "logs"


def namer(name):
    return name + ".gz"


def rotator(source, dest):
    with open(source, "rb") as f_in, gzip.open(dest, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    os.remove(source)


loggers: dict[str, logging.Logger] = {}


class ConsoleLogFilter(logging.Filter):
    MAX_JSON_LENGTH = 120
    MAX_LINE_LENGTH = 150

    def filter(self, record: logging.LogRecord) -> bool:
        msg = str(record.getMessage())

        msg = re.sub(r"\[corr=[^\]]+\]\s*", "", msg)

        if msg.strip() == "- -- -- -- -- -- -- -- -- -":
            record.msg = "[dim]---[/dim]"
            record.args = ()
            return True

        if msg.startswith("COMMAND:"):
            simplified = self._simplify_command(msg)
            record.msg = f"[dim]{simplified}[/dim]"
            record.args = ()
            return True

        if msg.startswith("RETURN CODE:"):
            if "RETURN CODE: 0" in msg:
                return False
            record.msg = f"[yellow]{msg}[/yellow]"
            record.args = ()
            return True

        if msg.startswith("{") and len(msg) > self.MAX_JSON_LENGTH:
            if '"Name":' in msg or '"Image":' in msg:
                truncated = msg[: self.MAX_JSON_LENGTH] + "... [dim][see log file][/dim]"
                record.msg = truncated
                record.args = ()
            else:
                truncated = msg[: self.MAX_JSON_LENGTH] + "... [dim][truncated][/dim]"
                record.msg = truncated
                record.args = ()
            return True

        if len(msg) > self.MAX_LINE_LENGTH and not msg.startswith("["):
            truncated = msg[: self.MAX_LINE_LENGTH] + "... [dim][truncated][/dim]"
            record.msg = truncated
            record.args = ()
            return True

        record.msg = msg
        record.args = ()
        return True

    def _simplify_command(self, cmd_line: str) -> str:
        cmd = cmd_line.replace("COMMAND: ", "")

        simplifications = [
            (r"docker compose -f [^\s]+ exec (?:--user \w+ )?(?:--workdir [^\s]+ )?(\w+) (.+)", r"[\1] \2"),
            (r"docker compose -f [^\s]+ (up|down|ps|start|stop|restart) (.+)", r"compose \1 \2"),
            (r"docker (\w+) (.+)", r"docker \1 ..."),
        ]

        for pattern, replacement in simplifications:
            match = re.search(pattern, cmd)
            if match:
                try:
                    simplified = re.sub(pattern, replacement, cmd)
                    if len(simplified) > 100:
                        simplified = simplified[:97] + "..."
                    return f"COMMAND: {simplified}"
                except Exception:
                    continue

        if len(cmd) > 80:
            return f"COMMAND: {cmd[:77]}..."

        return f"COMMAND: {cmd}"


def _add_console_handler(logger: logging.Logger, console_level: str) -> None:
    for handler in logger.handlers[:]:
        if isinstance(handler, RichHandler):
            logger.removeHandler(handler)

    try:
        from fmd.commands._utils import get_printer

        printer = get_printer()
        if hasattr(printer, "stderr"):
            console_handler = RichHandler(
                level=getattr(logging, console_level),
                rich_tracebacks=True,
                tracebacks_show_locals=True,
                show_time=False,
                show_path=False,
                show_level=True,
                markup=True,
                console=printer.stderr,
            )
        else:
            console_handler = RichHandler(
                level=getattr(logging, console_level),
                rich_tracebacks=True,
                tracebacks_show_locals=True,
                show_time=False,
                show_path=False,
                show_level=True,
                markup=True,
            )
    except Exception:
        console_handler = RichHandler(
            level=getattr(logging, console_level),
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            show_time=False,
            show_path=False,
            show_level=True,
            markup=True,
        )

    console_handler.setFormatter(logging.Formatter("%(message)s"))
    console_handler.addFilter(ConsoleLogFilter())
    logger.addHandler(console_handler)


def _update_console_handler(logger: logging.Logger, console_level: str | None) -> None:
    if console_level:
        _add_console_handler(logger, console_level)
    else:
        for handler in logger.handlers[:]:
            if isinstance(handler, RichHandler):
                logger.removeHandler(handler)


def get_logger(
    log_dir=CLI_LOG_DIRECTORY,
    log_file_name="fmd",
    console_level: str | None = None,
    file_level: str = "DEBUG",
) -> logging.Logger:
    logPath = log_dir / f"{log_file_name}.log"

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        print(f"FATAL: Logging not working. {e}")
        raise

    logger_exists = loggers.get(log_file_name) is not None
    if logger_exists:
        logger: logging.Logger | None = loggers.get(log_file_name)
    else:
        logger: logging.Logger | None = logging.getLogger(log_file_name)
        logger.setLevel(logging.DEBUG)

        handler = logging.handlers.RotatingFileHandler(logPath, "a+", maxBytes=10485760, backupCount=3)
        handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))
        handler.setLevel(getattr(logging, file_level.upper()))
        handler.rotator = rotator
        handler.namer = namer
        logger.addHandler(handler)

        loggers[log_file_name] = logger

    if logger and (not logger_exists or console_level is not None):
        _update_console_handler(logger, console_level)

    return logger
