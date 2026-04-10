import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

from fmd.commands._utils import load_config, build_runners, get_printer
from fmd.managers.release import ReleaseManager
from fmd.release_directory import BenchDirectory

SITE = "fm.localhost"
CONFIG = Path(__file__).parent / "test-fm.localhost.toml"
WORKSPACE = Path("/Users/aloksingh/frappe/sites/fm.localhost/workspace")
BENCH_PATH = WORKSPACE / "frappe-bench"
FMD = Path(__file__).parent / ".venv/bin/fmd"

PASS = []
FAIL = []


def check(label, condition):
    if condition:
        PASS.append(label)
        print(f"  PASS  {label}")
    else:
        FAIL.append(label)
        print(f"  FAIL  {label}")


def workspace_state():
    return {
        "bench_is_symlink": BENCH_PATH.is_symlink(),
        "bench_is_real_dir": BENCH_PATH.is_dir() and not BENCH_PATH.is_symlink(),
        "data_exists": (WORKSPACE / "deployment-data").exists(),
        "releases": sorted(d.name for d in WORKSPACE.iterdir() if d.name.startswith("release_") and d.is_dir()),
    }


print("\n== SETUP: ensure raw bench state ==")
pre = workspace_state()
print(f"  Current state: {pre}")
if pre["bench_is_symlink"]:
    print("  Bench is configured (symlink). Auto-unconfiguring...")
    setup_config = load_config(CONFIG)
    setup_ir, setup_er, setup_hr = build_runners(setup_config)
    setup_printer = get_printer()
    setup_rm = ReleaseManager(setup_config, setup_ir, setup_er, setup_hr, setup_printer)
    actual_release = BENCH_PATH.resolve()
    setup_rm.new = BenchDirectory(actual_release)
    setup_rm._rollback_configure(renamed=True)
    pre = workspace_state()
    print(f"  After auto-unconfigure: {pre}")

check("bench is a real dir (not symlink)", pre["bench_is_real_dir"])
check("no deployment-data", not pre["data_exists"])
check("no release dirs", len(pre["releases"]) == 0)
if FAIL:
    print("  Preconditions not met. Aborting.")
    sys.exit(1)


print("\n== STEP 1: SiteAlreadyConfigured guard (needs configured state) ==")
result = subprocess.run(
    [str(FMD), "release", "configure", SITE, "--no-backups"], capture_output=True, text=True, timeout=300
)
if result.returncode != 0:
    print(f"  configure failed unexpectedly: {result.stderr[-300:]}")
    sys.exit(1)
result2 = subprocess.run([str(FMD), "release", "configure", SITE], capture_output=True, text=True)
check("configure on configured site exits non-zero", result2.returncode != 0)
check("error is SiteAlreadyConfigured", "SiteAlreadyConfigured" in result2.stdout + result2.stderr)
print(f"  exit={result2.returncode}")


print("\n== STEP 2: Restore to raw bench state via _rollback_configure with correct release target ==")
configured = workspace_state()
print(f"  Configured state: {configured}")

config = load_config(CONFIG)
image_runner, exec_runner, host_runner = build_runners(config)
printer = get_printer()
rm = ReleaseManager(config, image_runner, exec_runner, host_runner, printer)

actual_release = BENCH_PATH.resolve()
print(f"  Actual release dir: {actual_release}")

rm.new = BenchDirectory(actual_release)

rm._rollback_configure(renamed=True)

restored = workspace_state()
print(f"  After un-configure: {restored}")
check("bench is real dir after un-configure", restored["bench_is_real_dir"])
check("deployment-data gone after un-configure", not restored["data_exists"])
check("release dir removed after un-configure", len(restored["releases"]) == 0)


print("\n== STEP 3a: configure() with failure BEFORE rename (inside configure_data_dir) → renamed=False path ==")
before_3a = workspace_state()
print(f"  Before: {before_3a}")

config3a = load_config(CONFIG)
image_runner3a, exec_runner3a, host_runner3a = build_runners(config3a)
rm3a = ReleaseManager(config3a, image_runner3a, exec_runner3a, host_runner3a, printer)

# Patch configure_data_dir to do nothing (simulates failure before any data is moved).
# renamed=False path: bench is still a real dir, rollback is a no-op.
raised_3a = None
with patch.object(rm3a.symlink_service, "configure_data_dir", side_effect=RuntimeError("injected pre-rename failure")):
    try:
        rm3a.configure(backups=False)
    except RuntimeError as e:
        raised_3a = e

after_3a = workspace_state()
print(f"  After: {after_3a}")
check("3a: configure raised RuntimeError", raised_3a is not None and "injected pre-rename failure" in str(raised_3a))
check("3a: bench still real dir (nothing touched)", after_3a["bench_is_real_dir"])
check("3a: no deployment-data created", not after_3a["data_exists"])
check("3a: no release dirs created", len(after_3a["releases"]) == 0)


print("\n== STEP 3b: configure() with injected failure AFTER rename → test _rollback_configure(renamed=True) ==")
before_test = workspace_state()
print(f"  Before: {before_test}")

config2 = load_config(CONFIG)
image_runner2, exec_runner2, host_runner2 = build_runners(config2)
rm2 = ReleaseManager(config2, image_runner2, exec_runner2, host_runner2, printer)

raised = None
with patch.object(rm2.symlink_service, "configure_symlinks", side_effect=RuntimeError("injected failure")):
    try:
        rm2.configure(backups=False)
    except RuntimeError as e:
        raised = e

after_test = workspace_state()
print(f"  After failed configure: {after_test}")

check("3b: configure raised RuntimeError", raised is not None and "injected failure" in str(raised))
check("3b: bench is real dir (rollback restored it)", after_test["bench_is_real_dir"])
check("3b: deployment-data removed by rollback", not after_test["data_exists"])
check("3b: no release dir left after rollback", len(after_test["releases"]) == 0)


print("\n== STEP 4: clean configure after successful rollback ==")
result3 = subprocess.run(
    [str(FMD), "release", "configure", SITE, "--no-backups"],
    capture_output=True,
    text=True,
    timeout=300,
)
print(result3.stdout[-1500:] if result3.stdout else "")
if result3.stderr:
    print("STDERR:", result3.stderr[-300:])
check("clean configure exits 0", result3.returncode == 0)

final = workspace_state()
print(f"  Final: {final}")
check("bench is symlink after clean configure", final["bench_is_symlink"])
check("deployment-data exists after clean configure", final["data_exists"])
check("release dir exists after clean configure", len(final["releases"]) > 0)


print(f"\n{'=' * 50}")
print(f"  {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("  FAILED:", FAIL)
    sys.exit(1)
