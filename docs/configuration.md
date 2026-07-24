# Configuration

fmd is driven by a TOML config file (conventionally `site.toml`), passed with
`-c/--config`. It replaces long command lines and makes deployments reusable and
version-controllable.

This page covers the most-used keys per section. The exhaustive, annotated schema
lives in [`example-config.toml`](https://github.com/rtcamp/fmd/blob/main/example-config.toml)
at the repo root — consult it for every field and default.

## Config file basics

```toml
site_name = "mysite.localhost"   # required
bench_name = ""                   # FM bench/container name; defaults to site_name
github_token = "${GITHUB_TOKEN}"  # PAT for private repos; empty = public only
verbose = false                   # verbose output for all commands
```

- `site_name` is the only required key and must match a site in Frappe Manager.
- `bench_name` defaults to `site_name`; set it only when the bench directory differs.
- String values support `${VAR}` / `$VAR` environment substitution; undefined
  variables are left untouched. Non-string values are not substituted.

Reference the file from any command:

```bash
fmd deploy pull --config site.toml
```

**Precedence:** CLI flags > config file values > built-in defaults.

## Apps

Each app is a repeated `[[apps]]` block, installed in order:

```toml
[[apps]]
repo = "frappe/frappe"   # "org/repo" or full GitHub URL
ref = "version-15"        # branch, tag, or commit

[[apps]]
repo = "frappe/erpnext"
ref = "version-15"
```

Key per-app fields:

| Field | Purpose |
| --- | --- |
| `repo` | `org/repo` or full URL |
| `ref` | branch, tag, or commit |
| `subdir_path` | path to the app inside a monorepo (e.g. `apps/my-app`) |
| `symlink` | symlink the app instead of copying (dev, or monorepo subdir apps) |

**Shorthand** on the CLI via `--app`:

```
org/repo:ref            org/repo:ref:subdir/path
```

```bash
fmd deploy pull mysite.localhost --app my-org/monorepo:main:apps/my-app
```

### Monorepo apps

Point `subdir_path` at the app directory within a larger repo. fmd clones the full
repo and exposes the subdirectory as a normal Frappe app; `symlink = true` is
recommended for subdir apps. Set `[release] symlink_subdir_apps = true` to symlink
all subdir apps at once.

```toml
[[apps]]
repo = "my-org/monorepo"
ref = "main"
subdir_path = "apps/my-app"
symlink = true
```

## [release]

Controls how a release is built.

```toml
[release]
releases_retain_limit = 7   # older releases pruned automatically
python_version = ""          # e.g. "3.12"; empty = system default
node_version = ""            # e.g. "20"; empty = fnm default
platform = ""                # e.g. "linux/arm64" for cross-arch builds
mode = ""                    # "exec" (default) or "image"
```

- `mode = "exec"` builds in the running docker-compose containers; `image` builds in
  a temporary container (works without running services, useful in CI). `--build-dir`
  implies image mode.
- `use_fc_apps` / `use_fc_deps` pull the app list and Python version from Frappe
  Cloud (see [Frappe Cloud sync](#frappe-cloud-sync)).
- Global build [hooks](#hooks) may be set here as fallbacks for apps without their own.

## [switch]

Controls runtime behavior when a release is activated (`release switch`, and the
switch step of `deploy pull`/`ship`).

```toml
[switch]
migrate = true                       # run bench migrate
migrate_timeout = 300
migrate_command = ""                 # override the migrate command
maintenance_mode = true              # see Maintenance mode below
maintenance_mode_phases = ["migrate"]
backups = true                       # DB backup before switch
rollback = false                     # auto-revert to previous release on failure
search_replace = true                # rewrite site name in DB after restore
install_apps = true                  # install apps into the site during switch
```

- `migrate` runs `bench migrate` during the switch; `migrate_command` overrides it.
- `backups` snapshots the DB into `deployment-backup/` before switching.
- `rollback = true` silently reverts on failure — enable only in unattended
  environments; otherwise fix forward or `fmd release switch` manually.
- `install_apps = false` clones apps into the release but skips installing them into
  the site (CLI: `--no-install-apps`).
- Worker draining: `drain_workers`, `drain_workers_timeout`, `skip_stale_workers`,
  `worker_kill_timeout`, and related poll/timeout keys govern how background workers
  are drained/killed before restart.
- `[switch.common_site_config]` and `[switch.site_config]` merge key/value pairs into
  the respective JSON files during switch.
- Restore keys `use_fc_db` and `restore_db_from_site` are covered in
  [Restoring a database](#restoring-a-database).

## Restoring a database

Two ways to seed this site's DB at switch time:

```toml
[switch]
use_fc_db = true                          # restore latest Frappe Cloud backup
restore_db_from_site = "other.localhost"  # restore from another local FM bench/site
```

- `use_fc_db` downloads and restores the latest Frappe Cloud backup (requires
  [`[fc]`](#frappe-cloud-sync) credentials).
- `restore_db_from_site` exports the DB from another local FM bench/site and restores
  it into this one.

!!! warning "Encryption key handling"
    For both flows, fmd copies the **source site's `encryption_key`** into the target
    `site_config.json` **before** `bench migrate`, so Fernet-encrypted secrets (API
    keys, SMTP/OAuth passwords in `__Auth`) stay decryptable. Frappe has **no
    key-rotation command** — copying the key is the documented method. When
    `search_replace` is on, the old site name is rewritten to the new one.

    This is distinct from `backup_encryption_key`, which only GPG-encrypts backup
    *files* when the `encrypt_backup` system setting is on — unrelated to this flow.

## Frappe Cloud sync

```toml
[fc]
api_key = ""
api_secret = ""
site_name = ""    # your FC site
team_name = ""

[release]
use_fc_apps = true   # import app list + commit hashes from FC (merged with local)
use_fc_deps = true   # import python_version from FC (only if not set locally)

[switch]
use_fc_db = true     # restore latest FC DB backup at switch
```

- `use_fc_apps` overrides local `[[apps]]` refs with FC commit hashes while
  preserving local app config (hooks, `symlink`, `subdir_path`).
- `use_fc_deps` sets `python_version` from FC only when not explicitly configured
  locally.

## Hooks

Hooks are inline shell scripts run at specific lifecycle points. Values starting with
`host_` run on the **host**; the rest run **inside the build/switch container**.

**Build hooks** — 8 per app (also settable globally under `[release]` as fallbacks):

```toml
[[apps]]
repo = "my-org/my-app"
ref = "main"
before_bench_build = """
npm ci
npm run build:prod
"""
host_after_bench_build = 'curl -X POST "$WEBHOOK_URL" -d done'
```

| Container | Host |
| --- | --- |
| `before_bench_build` | `host_before_bench_build` |
| `after_bench_build` | `host_after_bench_build` |
| `before_python_install` | `host_before_python_install` |
| `after_python_install` | `host_after_python_install` |

**Restart hooks** — 4 under `[switch]`:

```toml
[switch]
before_restart = "bench --site all clear-cache"
host_after_restart = "curl https://healthcheck.io/ping/xyz"
```

`before_restart`, `after_restart` (container) and `host_before_restart`,
`host_after_restart` (host).

## Maintenance mode

Maintenance mode is **configuration only** — there is no `fmd maintenance` command and
no bypass tokens. It is controlled entirely by `[switch]`:

```toml
[switch]
maintenance_mode = true
maintenance_mode_phases = ["migrate"]   # valid: "drain", "migrate"
```

- `maintenance_mode` enables maintenance during switch operations.
- `maintenance_mode_phases` restricts *when* it is active. `["migrate"]` (default)
  enables it only during migration; `["drain", "migrate"]` covers both phases; an
  empty list applies it to all phases.

For zero-downtime code-only deploys, set `maintenance_mode = false` and
`migrate = false`. For schema changes, keep both on.

## Remote workers

Run background workers on a separate server, synced from the primary.

```toml
[remote_worker]
server_ip = ""        # IP/domain of the worker server
ssh_user = "frappe"
ssh_port = 22
include_dirs = []      # extra directories to sync
include_files = []     # extra files to sync (e.g. ".env")
```

Enable ports and sync releases:

```bash
fmd remote-worker enable mysite.localhost --rw-server 192.168.1.100
fmd remote-worker sync   mysite.localhost --rw-server 192.168.1.100
```

`enable` opens the Redis/MariaDB ports the worker needs; `sync` copies the active
release to it. Set `[switch] sync_workers = true` to sync automatically after each
successful switch.

## Ship & remote

Ship mode builds the release locally or in CI and rsyncs it to a remote host, which
only needs SSH + rsync + uv.

```toml
[ship]
host = ""              # remote hostname/IP (required for ship)
ssh_user = "frappe"
ssh_port = 22
remote_path = ""       # empty = auto-detect $HOME/frappe/sites/<site>
fmd_source = ""        # git URL / local path to run fmd remotely via uvx; empty = auto
rsync_options = []     # extra rsync flags, e.g. ["--bwlimit=10000"]
```

See [Deploy modes](deploy-modes.md) for pull vs ship, and
[GitHub Actions](github-actions.md) for CI/CD.
