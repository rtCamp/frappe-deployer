import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import fmd.commands._utils as _u
from fmd.commands._utils import load_config, set_verbose, parse_app_option

CONFIG = Path(__file__).parent / "test-fm.localhost.toml"

PASS = []
FAIL = []

_SENSITIVE_KEYWORDS = {"password", "secret", "token", "key", "credential", "private"}


def _mask_if_sensitive(label: str, value: object) -> str:
    if any(kw in label.lower() for kw in _SENSITIVE_KEYWORDS):
        return "[REDACTED]"
    return repr(value)


def check(label, got, expected):
    if got == expected:
        PASS.append(label)
        print(f"  PASS  {label}")
    else:
        FAIL.append(label)
        print(
            f"  FAIL  {label}  ->  expected {_mask_if_sensitive(label, expected)}, got {_mask_if_sensitive(label, got)}"
        )


def reset_verbose():
    _u._verbose = None


# -- fmd --verbose (global) ---------------------------------------------------
print("\n-- fmd --verbose (global) --")
set_verbose(True)
c = load_config(CONFIG)
check("--verbose sets verbose=True", c.verbose, True)
reset_verbose()

c = load_config(CONFIG)
check("no --verbose keeps verbose=False", c.verbose, False)

set_verbose(True)
c = load_config(CONFIG, overrides={"deploy": {"backups": True}})
check("--verbose + other overrides: verbose", c.verbose, True)
check("--verbose + other overrides: backups", c.deploy.backups, True)
reset_verbose()


# -- release configure --------------------------------------------------------
print("\n-- release configure --")
c = load_config(CONFIG, overrides={"deploy": {"backups": True}})
check("--backups overrides backups=false", c.deploy.backups, True)

c = load_config(CONFIG, overrides={"deploy": {"backups": False}})
check("--no-backups keeps backups=false", c.deploy.backups, False)

c = load_config(CONFIG, overrides={"release": {"symlink_subdir_apps": True}})
check("--symlink-subdir-apps overrides symlink_subdir_apps=false", c.release.symlink_subdir_apps, True)

c = load_config(CONFIG, overrides={"uv": False})
check("--no-uv overrides uv=true", c.uv, False)

c = load_config(CONFIG, overrides={"python_version": "3.12"})
check("--python-version overrides None", c.python_version, "3.12")


# -- release create -----------------------------------------------------------
print("\n-- release create --")
c = load_config(CONFIG, overrides={"release": {"releases_retain_limit": 3}})
check("--releases-retain-limit 3 overrides 7", c.release.releases_retain_limit, 3)

c = load_config(CONFIG, overrides={"release": {"releases_retain_limit": 1}})
check("--releases-retain-limit 1", c.release.releases_retain_limit, 1)

c = load_config(CONFIG, overrides={"release": {"symlink_subdir_apps": True, "releases_retain_limit": 2}})
check("combined release flags: symlink_subdir_apps", c.release.symlink_subdir_apps, True)
check("combined release flags: releases_retain_limit", c.release.releases_retain_limit, 2)


# -- release switch -----------------------------------------------------------
print("\n-- release switch --")
c = load_config(CONFIG, overrides={"deploy": {"migrate": True}})
check("--migrate overrides migrate=false", c.deploy.migrate, True)

c = load_config(CONFIG, overrides={"deploy": {"migrate_timeout": 600}})
check("--migrate-timeout 600 overrides 300", c.deploy.migrate_timeout, 600)

c = load_config(CONFIG, overrides={"deploy": {"maintenance_mode": False}})
check("--no-maintenance-mode overrides maintenance_mode=true", c.deploy.maintenance_mode, False)

c = load_config(CONFIG, overrides={"deploy": {"backups": True}})
check("--backups overrides backups=false", c.deploy.backups, True)

c = load_config(CONFIG, overrides={"deploy": {"rollback": True}})
check("--rollback overrides rollback=false", c.deploy.rollback, True)

c = load_config(CONFIG, overrides={"deploy": {"search_replace": False}})
check("--no-search-replace overrides search_replace=true", c.deploy.search_replace, False)

c = load_config(CONFIG, overrides={"deploy": {"drain_workers": True}})
check("--drain-workers overrides drain_workers=false", c.deploy.drain_workers, True)

c = load_config(CONFIG, overrides={"deploy": {"sync_workers": True}})
check("--sync-workers overrides sync_workers=false", c.deploy.sync_workers, True)


# -- deploy pull --------------------------------------------------------------
print("\n-- deploy pull --")
c = load_config(CONFIG, overrides={"site_name": "other.localhost"})
check("--site-name overrides site_name", c.site_name, "other.localhost")

c = load_config(CONFIG, overrides={"github_token": "ghp_test"})
check("--github-token overrides None", c.github_token, "ghp_test")

c = load_config(
    CONFIG,
    overrides={
        "deploy": {
            "migrate": True,
            "backups": True,
            "maintenance_mode": False,
            "rollback": True,
            "search_replace": False,
            "drain_workers": True,
            "sync_workers": True,
            "migrate_timeout": 120,
        }
    },
)
check("pull: migrate=True", c.deploy.migrate, True)
check("pull: backups=True", c.deploy.backups, True)
check("pull: maintenance_mode=False", c.deploy.maintenance_mode, False)
check("pull: rollback=True", c.deploy.rollback, True)
check("pull: search_replace=False", c.deploy.search_replace, False)
check("pull: drain_workers=True", c.deploy.drain_workers, True)
check("pull: sync_workers=True", c.deploy.sync_workers, True)
check("pull: migrate_timeout=120", c.deploy.migrate_timeout, 120)

c = load_config(CONFIG, overrides={"release": {"releases_retain_limit": 5, "symlink_subdir_apps": True}})
check("pull: releases_retain_limit=5", c.release.releases_retain_limit, 5)
check("pull: symlink_subdir_apps=True", c.release.symlink_subdir_apps, True)

c = load_config(
    CONFIG, overrides={"fc": {"api_key": "k", "api_secret": "s", "site_name": "x.frappe.cloud", "team_name": "t"}}
)
check("pull: fc.api_key", c.fc.api_key, "k")
check("pull: fc.api_secret", c.fc.api_secret, "s")
check("pull: fc.site_name", c.fc.site_name, "x.frappe.cloud")
check("pull: fc.team_name", c.fc.team_name, "t")

c = load_config(
    CONFIG,
    overrides={
        "release": {
            "use_fc_deps": True,
            "use_fc_apps": True,
        },
        "switch": {
            "use_fc_db": True,
        },
    },
)
check("pull: release.use_fc_deps=True", c.release.use_fc_deps, True)
check("pull: switch.use_fc_db=True", c.switch.use_fc_db, True)
check("pull: release.use_fc_apps=True", c.release.use_fc_apps, True)

c = load_config(CONFIG, overrides={"remote_worker": {"server_ip": "10.0.0.1", "ssh_user": "deploy", "ssh_port": 2222}})
check("pull: rw.server_ip", c.remote_worker.server_ip, "10.0.0.1")
check("pull: rw.ssh_user", c.remote_worker.ssh_user, "deploy")
check("pull: rw.ssh_port", c.remote_worker.ssh_port, 2222)


# -- deploy ship --------------------------------------------------------------
print("\n-- deploy ship --")
c = load_config(CONFIG, overrides={"uv": False})
check("ship: --no-uv overrides uv=true", c.uv, False)

c = load_config(
    CONFIG,
    overrides={
        "deploy": {
            "migrate": True,
            "backups": True,
            "rollback": True,
            "search_replace": False,
            "drain_workers": True,
            "sync_workers": True,
        }
    },
)
check("ship: migrate=True", c.deploy.migrate, True)
check("ship: backups=True", c.deploy.backups, True)
check("ship: rollback=True", c.deploy.rollback, True)
check("ship: search_replace=False", c.deploy.search_replace, False)
check("ship: drain_workers=True", c.deploy.drain_workers, True)
check("ship: sync_workers=True", c.deploy.sync_workers, True)


# -- remote-worker enable / sync ----------------------------------------------
print("\n-- remote-worker enable / sync --")
c = load_config(CONFIG, overrides={"remote_worker": {"server_ip": "192.168.1.50"}})
check("--rw-server overrides None", c.remote_worker.server_ip, "192.168.1.50")

c = load_config(CONFIG, overrides={"remote_worker": {"server_ip": "192.168.1.50", "ssh_user": "ubuntu"}})
check("--rw-user sets ssh_user", c.remote_worker.ssh_user, "ubuntu")

c = load_config(CONFIG, overrides={"remote_worker": {"server_ip": "192.168.1.50", "ssh_port": 2222}})
check("--rw-port sets ssh_port", c.remote_worker.ssh_port, 2222)


# -- parse_app_option ---------------------------------------------------------
print("\n-- --app flag parsing --")
apps = parse_app_option(["frappe/frappe:version-15"])
check("app: repo", apps[0]["repo"], "frappe/frappe")
check("app: ref", apps[0]["ref"], "version-15")
check("app: no subdir_path", "subdir_path" not in apps[0], True)

apps = parse_app_option(["myorg/custom-app:main:apps/custom-app"])
check("app+subdir: repo", apps[0]["repo"], "myorg/custom-app")
check("app+subdir: ref", apps[0]["ref"], "main")
check("app+subdir: subdir_path", apps[0]["subdir_path"], "apps/custom-app")

apps = parse_app_option(["frappe/frappe:version-15", "frappe/erpnext:version-15"])
check("multiple --app: count", len(apps), 2)
check("multiple --app: second repo", apps[1]["repo"], "frappe/erpnext")


# -- new config from flags (create_if_missing) --------------------------------
print("\n-- new config from flags (create_if_missing) --")

with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
    tmp = Path(f.name)
os.unlink(tmp)

c = load_config(
    tmp,
    overrides={"site_name": "new.localhost", "deploy": {"backups": False, "migrate": False}},
    create_if_missing=True,
)
check("new config: site_name", c.site_name, "new.localhost")
check("new config: backups=False", c.deploy.backups, False)
check("new config: migrate=False", c.deploy.migrate, False)
check("new config file created on disk", tmp.exists(), True)
tmp.unlink(missing_ok=True)


# -- fileless invocation (no config_path, --site-name only) -------------------
print("\n-- fileless invocation (config_path=None, --site-name) --")

c = load_config(None, overrides={"site_name": "noconfig.localhost"})
check("fileless: site_name set", c.site_name, "noconfig.localhost")

c = load_config(None, overrides={"site_name": "noconfig.localhost", "deploy": {"backups": True}})
check("fileless: backups override", c.deploy.backups, True)

c = load_config(
    None, overrides={"site_name": "noconfig.localhost", "deploy": {"migrate": True, "migrate_timeout": 120}}
)
check("fileless: migrate=True", c.deploy.migrate, True)
check("fileless: migrate_timeout=120", c.deploy.migrate_timeout, 120)

c = load_config(None, overrides={"site_name": "noconfig.localhost", "deploy": {"maintenance_mode": True}})
check("fileless: maintenance_mode=True", c.deploy.maintenance_mode, True)

c = load_config(None, overrides={"site_name": "noconfig.localhost", "release": {"releases_retain_limit": 5}})
check("fileless: releases_retain_limit=5", c.release.releases_retain_limit, 5)

c = load_config(None, overrides={"site_name": "noconfig.localhost", "release": {"symlink_subdir_apps": True}})
check("fileless: symlink_subdir_apps=True", c.release.symlink_subdir_apps, True)

c = load_config(None, overrides={"site_name": "noconfig.localhost", "uv": False})
check("fileless: uv=False", c.uv, False)

c = load_config(None, overrides={"site_name": "noconfig.localhost", "github_token": "ghp_fileless"})
check("fileless: github_token", c.github_token, "ghp_fileless")

c = load_config(
    None,
    overrides={
        "site_name": "noconfig.localhost",
        "remote_worker": {"server_ip": "10.1.2.3", "ssh_user": "ops", "ssh_port": 22},
    },
)
check("fileless: rw.server_ip", c.remote_worker.server_ip, "10.1.2.3")
check("fileless: rw.ssh_user", c.remote_worker.ssh_user, "ops")
check("fileless: rw.ssh_port", c.remote_worker.ssh_port, 22)

# missing site_name should raise
try:
    load_config(None, overrides=None)
    check("fileless: missing site_name raises", False, True)
except (ValueError, Exception):
    check("fileless: missing site_name raises", True, True)

set_verbose(True)
c = load_config(None, overrides={"site_name": "noconfig.localhost"})
check("fileless: --verbose sets verbose=True", c.verbose, True)
reset_verbose()


# -- summary ------------------------------------------------------------------
print(f"\n{'=' * 54}")
print(f"  {len(PASS)} passed  /  {len(FAIL)} failed  /  {len(PASS) + len(FAIL)} total")
if FAIL:
    print("\nFailed:")
    for f in FAIL:
        print(f"  - {f}")
    sys.exit(1)
