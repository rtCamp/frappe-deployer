#!/usr/bin/env python3
"""
test_runtime_symlinks.py

Tests the release-isolated runtime symlink/env-var approach for .uv and .fnm on fm.localhost.

What this validates:
  1. HOST SYMLINK RESOLUTION
     workspace/.fnm as a relative symlink to a release's .fnm/ — does the absolute
     alias inside (.fnm/aliases/default → /workspace/.fnm/node-versions/...) still
     resolve inside a container with a full workspace mount?

  2. BUILD CONTAINER — fnm via extra volume mount
     _run_in_image only mounts release_dir:/workspace/frappe-bench.
     Strategy: also mount {release}/.fnm:/workspace/.fnm
     Does `node --version` work inside the build container?

  3. BUILD CONTAINER — fnm via FNM_DIR env var
     Alternative: set FNM_DIR=/workspace/frappe-bench/.fnm + PATH prepend.
     Does `node --version` work this way?

  4. BUILD CONTAINER — uv Python via UV_PYTHON_INSTALL_DIR
     Set UV_PYTHON_INSTALL_DIR=/workspace/frappe-bench/.uv/python
     Run `uv venv env`, then inspect env/bin/python — does it point inside the release's .uv/?

  5. PYTHON ROLLBACK ISOLATION
     Create two fake release dirs each with a seeded .uv copy.
     Simulate creating a venv in release A, then switching to release B.
     The venv python symlink in release A must still resolve through release A's .uv/,
     not through workspace/.uv (which would change on switch).

  6. RUNTIME NODE — workspace/.fnm as symlink
     With workspace mounted at /workspace, does /workspace/.fnm/aliases/default/bin/node
     resolve correctly when workspace/.fnm is a symlink to release_dir/.fnm/?
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE = Path("/Users/aloksingh/frappe/sites/fm.localhost/workspace")
IMAGE = "ghcr.io/rtcamp/frappe-manager-frappe:v0.20.0.dev0"

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
SKIP = "\033[33mSKIP\033[0m"
INFO = "\033[34mINFO\033[0m"

results = []


def check(name, passed, detail=""):
    status = PASS if passed else FAIL
    print(f"  [{status}] {name}")
    if detail:
        for line in detail.strip().splitlines():
            print(f"         {line}")
    results.append((name, bool(passed) if passed is not None else None))


def section(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def docker_run(volumes: list[str], command: str, env: dict | None = None) -> tuple[int, str]:

    cmd = ["docker", "run", "--rm", "--user", "frappe", "--entrypoint", "/bin/bash"]
    for v in volumes:
        cmd += ["-v", v]
    if env:
        for k, v in env.items():
            cmd += ["-e", f"{k}={v}"]
    cmd += [IMAGE, "-c", f"source /etc/bash.bashrc 2>/dev/null; {command}"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout + result.stderr
    return result.returncode, output


def seed_release(release_path: Path) -> None:

    for name in (".uv", ".fnm"):
        src = WORKSPACE / name
        dst = release_path / name
        if src.exists() and not dst.is_symlink() and not dst.exists():
            if src.is_symlink():
                src = src.resolve()
            shutil.copytree(src, dst, symlinks=True)


# ---------------------------------------------------------------------------
# Setup: create a temp release dir for non-destructive tests
# ---------------------------------------------------------------------------
section("SETUP")

tmp_release = WORKSPACE / "release_test_symlinks_tmp"
if tmp_release.exists():
    shutil.rmtree(tmp_release)
tmp_release.mkdir()
for d in ("apps", "sites", "config/pids", "logs"):
    (tmp_release / d).mkdir(parents=True, exist_ok=True)

print(f"  [{INFO}] Seeding .uv and .fnm into {tmp_release.name}...")
seed_release(tmp_release)

has_uv = (tmp_release / ".uv").exists()
has_fnm = (tmp_release / ".fnm").exists()
check("tmp release has .uv seeded", has_uv)
check("tmp release has .fnm seeded", has_fnm)

# ---------------------------------------------------------------------------
# Test 1: Host symlink resolution
# ---------------------------------------------------------------------------
section("TEST 1 — Host symlink: workspace/.fnm → release/.fnm")

ws_fnm = WORKSPACE / ".fnm"
ws_fnm_was_symlink = ws_fnm.is_symlink()
print(f"  [{INFO}] workspace/.fnm is currently a {'symlink' if ws_fnm_was_symlink else 'real dir'}")

original_alias = (WORKSPACE / ".fnm" / "aliases" / "default").resolve(strict=False)
print(f"  [{INFO}] .fnm/aliases/default resolved (host) → {original_alias}")

alias_path = WORKSPACE / ".fnm" / "aliases" / "default"
if alias_path.is_symlink():
    alias_target = os.readlink(str(alias_path))
    print(f"  [{INFO}] .fnm/aliases/default target text: {alias_target}")
    check(
        "aliases/default is an absolute container path (/workspace/.fnm/...)",
        alias_target.startswith("/workspace/.fnm/"),
        f"target = {alias_target}",
    )
else:
    check("aliases/default is a symlink", False, "not a symlink")

test_ws_fnm = WORKSPACE / ".fnm_test_symlink"
if test_ws_fnm.exists() or test_ws_fnm.is_symlink():
    test_ws_fnm.unlink()

rel_target = os.path.relpath(tmp_release / ".fnm", WORKSPACE)
os.symlink(rel_target, test_ws_fnm)
check("can create workspace/.fnm_test_symlink → release/.fnm", test_ws_fnm.is_symlink())

alias_via_symlink = test_ws_fnm / "aliases" / "default"
check(
    "aliases/default accessible via workspace symlink",
    alias_via_symlink.exists() or alias_via_symlink.is_symlink(),
)

test_ws_fnm.unlink()

# ---------------------------------------------------------------------------
# Test 2: BUILD CONTAINER — fnm via extra volume mount
# ---------------------------------------------------------------------------
section("TEST 2 — Build container: fnm via extra mount {release}/.fnm:/workspace/.fnm")

if not has_fnm:
    print(f"  [{SKIP}] No .fnm seeded, skipping")
    results.append(("build container fnm extra mount", None))
else:
    volumes = [
        f"{tmp_release}:/workspace/frappe-bench",
        f"{tmp_release / '.fnm'}:/workspace/.fnm",
    ]
    rc, out = docker_run(volumes, "node --version")
    passed = rc == 0 and re.search(r"v\d+\.\d+\.\d+", out)
    check("node --version works (extra .fnm mount)", passed, out.strip()[:200])

    rc2, out2 = docker_run(volumes, "which node && readlink -f $(which node)")
    check("node binary resolves inside release .fnm", rc2 == 0, out2.strip()[:200])

# ---------------------------------------------------------------------------
# Test 3: BUILD CONTAINER — fnm via FNM_DIR env var
# ---------------------------------------------------------------------------
section("TEST 3 — Build container: fnm via FNM_DIR=/workspace/frappe-bench/.fnm")

if not has_fnm:
    print(f"  [{SKIP}] No .fnm seeded, skipping")
    results.append(("build container fnm env var", None))
else:
    volumes = [f"{tmp_release}:/workspace/frappe-bench"]
    env = {
        "FNM_DIR": "/workspace/frappe-bench/.fnm",
        "PATH": "/workspace/frappe-bench/.fnm/aliases/default/bin:/usr/local/bin:/usr/bin:/bin",
    }
    rc, out = docker_run(volumes, "node --version", env=env)
    passed = rc == 0 and re.search(r"v\d+\.\d+\.\d+", out)
    check("node --version works (FNM_DIR env var)", passed, out.strip()[:200])

    rc2, out2 = docker_run(
        volumes,
        "readlink -f /workspace/frappe-bench/.fnm/aliases/default/bin/node",
        env=env,
    )
    check("node binary is inside release .fnm", rc2 == 0, out2.strip()[:200])

# ---------------------------------------------------------------------------
# Test 4: BUILD CONTAINER — uv Python via UV_PYTHON_INSTALL_DIR
# ---------------------------------------------------------------------------
section("TEST 4 — Build container: uv venv with UV_PYTHON_INSTALL_DIR inside release")

if not has_uv:
    print(f"  [{SKIP}] No .uv seeded, skipping")
    results.append(("uv venv with UV_PYTHON_INSTALL_DIR", None))
else:
    volumes = [f"{tmp_release}:/workspace/frappe-bench"]
    env = {
        "UV_PYTHON_INSTALL_DIR": "/workspace/frappe-bench/.uv/python",
        "PATH": "/workspace/frappe-bench/.uv/python-default/bin:/usr/local/bin:/usr/bin:/bin",
    }
    rc, out = docker_run(volumes, "cd /workspace/frappe-bench && uv venv env --allow-existing", env=env)
    check("uv venv env succeeds", rc == 0, out.strip()[:300])

    if rc == 0:
        venv_python = tmp_release / "env" / "bin" / "python"
        if venv_python.is_symlink():
            python_target = os.readlink(str(venv_python))
            print(f"  [{INFO}] env/bin/python → {python_target}")
            inside_release_uv = "/workspace/frappe-bench/.uv" in python_target
            check(
                "env/bin/python symlink target is inside release .uv/", inside_release_uv, f"target = {python_target}"
            )
            not_workspace_uv = "/workspace/.uv" not in python_target
            check(
                "env/bin/python does NOT reference workspace-level .uv/ (rollback safe)",
                not_workspace_uv,
                f"target = {python_target}",
            )
        else:
            check("env/bin/python is a symlink", False, str(venv_python))

    venv_dir = tmp_release / "env"
    if venv_dir.exists():
        shutil.rmtree(venv_dir)

# ---------------------------------------------------------------------------
# Test 5: PYTHON ROLLBACK ISOLATION — two releases, two venvs
# ---------------------------------------------------------------------------
section("TEST 5 — Python rollback isolation: two releases, independent .uv venvs")

tmp_release_b = WORKSPACE / "release_test_symlinks_tmp_b"
if tmp_release_b.exists():
    shutil.rmtree(tmp_release_b)
tmp_release_b.mkdir()
for d in ("apps", "sites", "config/pids", "logs"):
    (tmp_release_b / d).mkdir(parents=True, exist_ok=True)
seed_release(tmp_release_b)
has_uv_b = (tmp_release_b / ".uv").exists()

if not has_uv or not has_uv_b:
    print(f"  [{SKIP}] Missing .uv in one or both releases")
    results.append(("rollback Python isolation", None))
else:
    env = {"UV_PYTHON_INSTALL_DIR": "/workspace/frappe-bench/.uv/python"}

    rc_a, out_a = docker_run(
        [f"{tmp_release}:/workspace/frappe-bench"],
        "cd /workspace/frappe-bench && uv venv env",
        env=env,
    )
    check("venv created in release A", rc_a == 0, out_a.strip()[:200])

    rc_b, out_b = docker_run(
        [f"{tmp_release_b}:/workspace/frappe-bench"],
        "cd /workspace/frappe-bench && uv venv env",
        env=env,
    )
    check("venv created in release B", rc_b == 0, out_b.strip()[:200])

    venv_a_python = tmp_release / "env" / "bin" / "python"
    venv_b_python = tmp_release_b / "env" / "bin" / "python"

    if venv_a_python.is_symlink() and venv_b_python.is_symlink():
        target_a = os.readlink(str(venv_a_python))
        target_b = os.readlink(str(venv_b_python))
        print(f"  [{INFO}] release A env/bin/python → {target_a}")
        print(f"  [{INFO}] release B env/bin/python → {target_b}")

        check(
            "release A python points through /workspace/frappe-bench/.uv/",
            "/workspace/frappe-bench/.uv" in target_a,
        )
        check(
            "release B python points through /workspace/frappe-bench/.uv/",
            "/workspace/frappe-bench/.uv" in target_b,
        )
        check(
            "release A and B have identical symlink text (both go through frappe-bench)",
            target_a == target_b,
            f"A={target_a}  B={target_b}",
        )

        fake_bench = WORKSPACE / "frappe-bench-test-rollback"
        if fake_bench.exists() or fake_bench.is_symlink():
            fake_bench.unlink()
        fake_bench.symlink_to(os.path.relpath(tmp_release, WORKSPACE))

        resolved_via_a = Path(str(target_a).replace("/workspace/frappe-bench", str(fake_bench))).resolve(strict=False)
        print(f"  [{INFO}] resolved through A's bench symlink → {resolved_via_a}")
        check(
            "python resolves into release A's .uv/ when bench→A",
            str(tmp_release) in str(resolved_via_a),
        )

        fake_bench.unlink()
        fake_bench.symlink_to(os.path.relpath(tmp_release_b, WORKSPACE))
        resolved_via_b = Path(str(target_a).replace("/workspace/frappe-bench", str(fake_bench))).resolve(strict=False)
        print(f"  [{INFO}] resolved through B's bench symlink → {resolved_via_b}")
        check(
            "python from release A's venv resolves into release B's .uv/ when bench→B (expected!)",
            str(tmp_release_b) in str(resolved_via_b),
            "NOTE: this is the expected rollback behavior — bench symlink controls which .uv is used",
        )
        fake_bench.unlink()
    else:
        check("both venvs have python symlinks", False)

# ---------------------------------------------------------------------------
# Test 6: RUNTIME NODE — workspace/.fnm as symlink, full workspace mount
# ---------------------------------------------------------------------------
section("TEST 6 — Runtime node: workspace/.fnm symlink with full workspace mount")

if not has_fnm:
    print(f"  [{SKIP}] No .fnm seeded, skipping")
    results.append(("runtime node via workspace symlink", None))
else:
    ws_fnm_backup = WORKSPACE / ".fnm_real_backup"

    already_symlink = ws_fnm.is_symlink()
    if already_symlink:
        original_target = os.readlink(str(ws_fnm))
        print(f"  [{INFO}] workspace/.fnm is already a symlink → {original_target}, testing as-is")
        made_temp_symlink = False
    else:
        ws_fnm.rename(ws_fnm_backup)
        rel = os.path.relpath(tmp_release / ".fnm", WORKSPACE)
        os.symlink(rel, ws_fnm)
        made_temp_symlink = True
        print(f"  [{INFO}] Created workspace/.fnm → {rel} (will restore after test)")

    try:
        volumes = [f"{WORKSPACE}:/workspace"]
        rc, out = docker_run(
            volumes,
            "/workspace/.fnm/aliases/default/bin/node --version",
        )
        check(
            "node via /workspace/.fnm/aliases/default/bin/node works (full workspace mount)", rc == 0, out.strip()[:200]
        )

        rc2, out2 = docker_run(
            volumes,
            "readlink -f /workspace/.fnm/aliases/default/bin/node",
        )
        if rc2 == 0:
            node_resolved = out2.strip()
            print(f"  [{INFO}] node resolved → {node_resolved}")
            check(
                "node resolves through workspace symlink into release's .fnm",
                tmp_release.name in node_resolved or "release_test_symlinks_tmp" in node_resolved,
                node_resolved,
            )
    finally:
        if made_temp_symlink:
            ws_fnm.unlink()
            ws_fnm_backup.rename(ws_fnm)
            print(f"  [{INFO}] Restored workspace/.fnm to real dir")

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
section("CLEANUP")
for path in [
    tmp_release,
    tmp_release_b,
    WORKSPACE / ".fnm_test_symlink",
    WORKSPACE / "frappe-bench-test-rollback",
]:
    if path.exists() or path.is_symlink():
        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
print(f"  [{INFO}] Temp release dirs removed")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
section("SUMMARY")
passed = sum(1 for _, r in results if r is True)
failed = sum(1 for _, r in results if r is False)
skipped = sum(1 for _, r in results if r is None)
total = len(results)

for name, r in results:
    status = PASS if r is True else (SKIP if r is None else FAIL)
    print(f"  [{status}] {name}")

print(f"\n  {passed}/{total - skipped} passed  ({skipped} skipped)")
sys.exit(0 if failed == 0 else 1)
