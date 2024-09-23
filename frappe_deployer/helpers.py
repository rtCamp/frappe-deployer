import datetime
from pathlib import Path

def gen_name_with_timestamp(base_name: str):
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename = f"{base_name}_{timestamp}"
    return filename

def get_relative_path(from_path: Path, to_path: Path) -> Path:
    return to_path.absolute().relative_to(from_path.absolute())

    # try:
    # except ValueError:

    #     # Handle the case where to_path is not a subpath of from_path
    #     return Path(os.path.relpath(to_path, start=from_path))
