"""Resolver overrides that must apply to every environment fmd creates.

``[tool.uv] override-dependencies`` in pyproject.toml only governs this repo's
own lock and sync. The deployment paths install fmd again on the target host
(``uv pip install`` for deploy pull, ``uvx --from`` for ship) and resolve from
scratch there, so they never see it. Without passing the same overrides
explicitly those hosts fall back to the transitive bounds and can install a
version we have deliberately moved off.

Keep this list in sync with pyproject.toml; tests/test_dependency_overrides.py
fails if the two drift.
"""

import shlex
import uuid
from pathlib import PurePosixPath

# frappe-manager caps cryptography at <50.0.0, which pins us to 49.0.0 and the
# PKCS#7 EnvelopedData decryption oracle (GHSA-g6cj-pr64-35w5). Drop this once
# frappe-manager relaxes its own bound.
DEPENDENCY_OVERRIDES: tuple[str, ...] = ("cryptography>=50.0.1,<51.0.0",)


def remote_overrides_path(home_dir: str) -> str:
    """Allocate a fresh path for the overrides file under a remote home.

    Takes the resolved home rather than a username: ship supports hosts where
    the login home is not /home/<user>, and a wrong directory would fail the
    write and abort the deployment.

    Unique per call, for two reasons. A shared name in a world-writable
    directory belongs to whoever deployed first. A shared name anywhere is
    worse for ship, where writing the file and running uvx are separate ssh
    round trips: a concurrent deployment from a revision with a different
    override set could replace the file in between and have this run resolve
    against it.
    """
    return str(PurePosixPath(home_dir) / ".fmd" / f"dependency-overrides-{uuid.uuid4().hex}.txt")


def overrides_file_contents() -> str:
    return "".join(f"{requirement}\n" for requirement in DEPENDENCY_OVERRIDES)


def write_remote_overrides_command(path: str) -> str:
    """Shell fragment that materialises the overrides file on a remote host."""
    parent = shlex.quote(str(PurePosixPath(path).parent))
    payload = shlex.quote(overrides_file_contents())
    return f"mkdir -p {parent} && printf %s {payload} > {shlex.quote(path)}"


def remove_remote_overrides_command(path: str) -> str:
    """Shell fragment that removes an overrides file written for one run."""
    return f"rm -f {shlex.quote(path)}"


def uv_overrides_args(path: str) -> list[str]:
    """Arguments that apply the overrides file to a uv invocation."""
    return ["--overrides", path]
