import datetime
from pathlib import Path
from typing import Generator
import re
import os
import git
from queue import Queue

def gen_name_with_timestamp(base_name: str):
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename = f"{base_name}_{timestamp}"
    return filename

def get_relative_path(from_path: Path, to_path: Path) -> Path:
    return Path(os.path.relpath(to_path.absolute().as_posix(),from_path.parent.absolute().as_posix()))

# class CloneProgress(git.remote.RemoteProgress):
#     def update(self, op_code, cur_count, max_count=None, message=''):
#         if message:
#             print(f"{message} ({cur_count}/{max_count})")

class CloneProgress(git.remote.RemoteProgress):
    def __init__(self):
        super().__init__()
        self.queue = Queue()

    def update(self, op_code, cur_count, max_count=None, message=''):
        if message:
            progress_message = f"{message} ({cur_count}/{max_count}df )"
            if cur_count == max_count:
                progress_message = None
            self.queue.put(progress_message)

    def get_progress(self) -> Generator[str, None, None]:
        while True:
            for line in iter(self.queue.get, None):
                yield 'stdout', line.encode()


def is_fqdn(name: str) -> bool:
    """Validates if the given name is a fully qualified domain name (FQDN)."""
    # Simple FQDN validation: contains at least one dot and does not start or end with a dot
    return bool(re.match(r'^(?!-)[A-Za-z0-9-]{1,63}(?<!-)\.(?!-)[A-Za-z0-9-]{1,63}(?<!-)$', name))
