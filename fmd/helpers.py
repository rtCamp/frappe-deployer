import datetime
import functools
import json
from pathlib import Path
from typing import Any, Generator
import re
import os

try:
    from frappe_manager.display_manager.DisplayManager import DisplayManager
except Exception:

    class DisplayManager:
        def print(self, *args, **kwargs):
            print(*args)


try:
    import git
except Exception:

    class _DummyRemoteProgress:
        def __init__(self, *args, **kwargs):
            pass

    class _DummyRemote:
        RemoteProgress = _DummyRemoteProgress

    git = type("git", (), {"remote": _DummyRemote})
import time
from contextlib import contextmanager
from queue import Queue

try:
    from frappe_manager.output_manager import RichOutputHandler as _RichOutputHandler

    richprint = _RichOutputHandler()
    if os.environ.get("CI", "").lower() == "true":
        richprint.set_interactive_mode(non_interactive_flag=True)
except Exception:

    def richprint(*args, **kwargs):
        print(*args)


def gen_name_with_timestamp(base_name: str):
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename = f"{base_name}_{timestamp}"
    return filename


def extract_timestamp(dir_name: str) -> int:
    try:
        timestamp_str = dir_name.split("_")[-1]
        return int(timestamp_str)
    except ValueError:
        return 0


def log_execution_time(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
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


def get_relative_path(from_path: Path, to_path: Path) -> Path:
    return Path(os.path.relpath(to_path.absolute().as_posix(), from_path.parent.absolute().as_posix()))


class CloneProgress(git.remote.RemoteProgress):
    def __init__(self):
        super().__init__()
        self.queue = Queue()

    def update(self, op_code, cur_count, max_count=None, message=""):
        if message:
            progress_message = f"{message} ({cur_count}/{max_count}df )"
            if cur_count == max_count:
                progress_message = None
            self.queue.put(progress_message)

    def get_progress(self) -> Generator[str, None, None]:
        while True:
            for line in iter(self.queue.get, None):
                yield "stdout", line.encode()


def is_fqdn(name: str) -> bool:
    return bool(re.match(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)\.(?!-)[A-Za-z0-9-]{1,63}(?<!-)$", name))


def get_json(file_path: Path) -> dict[Any, Any]:
    data = {}

    if file_path.exists():
        data = json.loads(file_path.read_text())

    return data


def update_json_keys_in_file_path(file_path: Path, data_to_update: dict[Any, Any], merge_data: bool = False) -> bool:
    json_data = get_json(file_path)

    if merge_data:
        result = data_to_update | json_data
    else:
        result = json_data | data_to_update
    file_path.write_text(json.dumps(result, ensure_ascii=False, indent=4))
    return True


def human_readable_time(seconds: float) -> str:
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or not parts:
        parts.append(f"{seconds:.2f}s")

    return " ".join(parts)


@contextmanager
def timing_manager(printer: DisplayManager, task: str = "Total", verbose: bool = False):
    if not verbose:
        yield
        return

    start_time = time.time()
    try:
        yield
    finally:
        end_time = time.time()
        elapsed_time = end_time - start_time
        printer.print(
            f"Time Taken: [bold yellow]{human_readable_time(elapsed_time)}[/bold yellow], {task}",
            emoji_code=":robot_face:",
        )
