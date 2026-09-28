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

# frappe-manager caps cryptography at <50.0.0, which pins us to 49.0.0 and the
# PKCS#7 EnvelopedData decryption oracle (GHSA-g6cj-pr64-35w5). Drop this once
# frappe-manager relaxes its own bound.
DEPENDENCY_OVERRIDES: tuple[str, ...] = ("cryptography>=50.0.1,<51.0.0",)

REMOTE_OVERRIDES_PATH = "/tmp/fmd-dependency-overrides.txt"


def overrides_file_contents() -> str:
    return "".join(f"{requirement}\n" for requirement in DEPENDENCY_OVERRIDES)


def write_remote_overrides_command(path: str = REMOTE_OVERRIDES_PATH) -> str:
    """Shell fragment that materialises the overrides file on a remote host."""
    return f"printf %s {shlex.quote(overrides_file_contents())} > {shlex.quote(path)}"


def uv_overrides_args(path: str = REMOTE_OVERRIDES_PATH) -> list[str]:
    """Arguments that apply the overrides file to a uv invocation."""
    return ["--overrides", path]
