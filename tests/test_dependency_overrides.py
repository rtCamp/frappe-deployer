import subprocess
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fmd.dependency_overrides import (
    DEPENDENCY_OVERRIDES,
    REMOTE_OVERRIDES_PATH,
    overrides_file_contents,
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

check("uv args point at the overrides file", uv_overrides_args(), ["--overrides", REMOTE_OVERRIDES_PATH])
check("uv args honour a custom path", uv_overrides_args("/tmp/other.txt"), ["--overrides", "/tmp/other.txt"])


# -- summary ------------------------------------------------------------------
print(f"\n{'=' * 54}")
print(f"  {len(PASS)} passed  /  {len(FAIL)} failed  /  {len(PASS) + len(FAIL)} total")
if FAIL:
    print("\nFailed:")
    for f in FAIL:
        print(f"  - {f}")
    sys.exit(1)
