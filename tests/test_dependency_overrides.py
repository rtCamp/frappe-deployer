import subprocess
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fmd.dependency_overrides import (
    DEPENDENCY_OVERRIDES,
    overrides_file_contents,
    remote_overrides_path,
    remove_remote_overrides_command,
    uv_overrides_args,
    write_remote_overrides_command,
)

ROOT = Path(__file__).parent.parent

PASS = []
FAIL = []


def check(label, got, expected):
    if got == expected:
        PASS.append(label)
        print(f"  PASS  {label}")
    else:
        FAIL.append(label)
        print(f"  FAIL  {label}  ->  expected {expected!r}, got {got!r}")


# -- the module and pyproject must not drift -----------------------------------
# pyproject governs our own lock, this module governs the remote installs. If
# they disagree, deployed hosts silently get a different resolution than the one
# we audited.
print("\n-- override definition --")

pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
declared = pyproject["tool"]["uv"]["override-dependencies"]

check("module matches pyproject override-dependencies", list(DEPENDENCY_OVERRIDES), declared)


# -- the remote fragment must reproduce the file verbatim ----------------------
# The fragment is interpolated into a remote shell command, so a quoting slip
# would write a mangled requirement and uv would resolve something else.
print("\n-- remote overrides file --")

contents = overrides_file_contents()
check("every requirement is on its own line", contents.splitlines(), list(DEPENDENCY_OVERRIDES))
check("file ends with a newline", contents.endswith("\n"), True)

target = Path("/tmp/fmd-overrides-test.txt")
target.unlink(missing_ok=True)
subprocess.run(["sh", "-c", write_remote_overrides_command(str(target))], check=True)
check("fragment writes the requirements verbatim", target.read_text(), contents)
target.unlink(missing_ok=True)

# a requirement carrying shell metacharacters must survive the round trip
import fmd.dependency_overrides as overrides_module  # noqa: E402

original = overrides_module.DEPENDENCY_OVERRIDES
overrides_module.DEPENDENCY_OVERRIDES = ('cryptography>=50.0.1; python_version >= "3.13"',)
try:
    target.unlink(missing_ok=True)
    subprocess.run(["sh", "-c", overrides_module.write_remote_overrides_command(str(target))], check=True)
    check(
        "shell metacharacters survive quoting",
        target.read_text(),
        'cryptography>=50.0.1; python_version >= "3.13"\n',
    )
    target.unlink(missing_ok=True)
finally:
    overrides_module.DEPENDENCY_OVERRIDES = original


# -- uv invocations must actually receive the file -----------------------------
print("\n-- uv arguments --")

check("uv args point at the given file", uv_overrides_args("/tmp/other.txt"), ["--overrides", "/tmp/other.txt"])


# -- each run must get its own file, under the resolved home -------------------
# ship writes the file and runs uvx as two separate ssh round trips, so a shared
# name lets a concurrent deploy swap the overrides in between. The helper takes
# a resolved home because ship supports hosts where it is not /home/<user>.
print("\n-- remote path --")

first = remote_overrides_path("/home/deploy")
second = remote_overrides_path("/home/deploy")

check("same home gets a fresh path per call", first == second, False)
check("path sits under the given home", first.startswith("/home/deploy/.fmd/"), True)
check("a nonstandard home is honoured", remote_overrides_path("/srv/ops").startswith("/srv/ops/.fmd/"), True)
check("no username is reconstructed", remote_overrides_path("/opt/u").startswith("/home/"), False)
check("write command creates the parent directory", "mkdir -p" in write_remote_overrides_command(first), True)

# the file is a per-run input, so it must not accumulate on the host
target.write_text("stale")
subprocess.run(["sh", "-c", remove_remote_overrides_command(str(target))], check=True)
check("remove command deletes the file", target.exists(), False)
subprocess.run(["sh", "-c", remove_remote_overrides_command(str(target))], check=True)
check("remove command tolerates a missing file", target.exists(), False)


# -- summary ------------------------------------------------------------------
print(f"\n{'=' * 54}")
print(f"  {len(PASS)} passed  /  {len(FAIL)} failed  /  {len(PASS) + len(FAIL)} total")
if FAIL:
    print("\nFailed:")
    for f in FAIL:
        print(f"  - {f}")
    sys.exit(1)
