# fmd — Frappe Manager Deployer

Zero-downtime Frappe deployments with atomic releases and rollback capability.

## Features

- **Atomic Releases**: Timestamped releases with instant symlink-based switching
- **Zero Downtime**: Workers drain gracefully, maintenance mode during migrations only
- **Rollback**: Keep N previous releases, instant rollback on failure
- **4 Deploy Modes**: pull, ship, bake, publish — dev to CI/CD production
- **Frappe Cloud Sync**: Import apps, deps, and DB backups from FC
- **Monorepo Support**: Symlink subdirectory apps for efficient workspace management

## Install

```bash
pip install frappe-deployer  # When available on PyPI

# Or from source
git clone <repo-url>
cd fmd
pip install -e .
```

**Requirements**: Python 3.10+, Docker + Frappe Manager

## Quick Start

```bash
# 1. Configure workspace (one-time setup)
fmd release configure site.localhost

# 2. Deploy Frappe + ERPNext
fmd deploy pull site.localhost \
  --app frappe/frappe:version-15 \
  --app frappe/erpnext:version-15 \
  --maintenance-mode --backups

# 3. Verify deployment
fmd release list site.localhost
fmd info site.localhost
```

## Key Commands

```bash
# Deploy: Full automated deployment (configure → create → switch)
fmd deploy pull <site>            # Minimal, uses config file
fmd deploy pull <site> --app frappe/frappe:version-15 --maintenance-mode

# Release: Manual control for CI/CD
fmd release configure <site>      # One-time workspace setup
fmd release create <site>         # Build new release (safe, no live changes)
fmd release switch <site> <rel>   # Atomically activate release
fmd release list <site>           # Show all releases

# Maintenance
fmd cleanup <site> -r 3 -b 5 -y   # Keep 3 releases, 5 backups
fmd search-replace <site> "old.com" "new.com" --dry-run

# Remote deploy (build locally, deploy to remote server)
fmd deploy ship --config site.toml
```

**App format**: `org/repo:ref` or `org/repo:ref:subdir/path` (for monorepos)

## Configuration

Create `site.toml`:

```toml
site_name = "site.localhost"
bench_name = "site"  # Optional, defaults to site_name
github_token = "ghp_xxx"  # For private repos

[[apps]]
repo = "frappe/frappe"
ref = "version-15"

[[apps]]
repo = "frappe/erpnext"
ref = "version-15"

[release]
releases_retain_limit = 7
symlink_subdir_apps = false  # Auto-symlink monorepo apps
python_version = "3.11"      # Pin Python version
use_fc_apps = false          # Import app list from Frappe Cloud
use_fc_deps = false          # Import Python version from FC

[switch]
migrate = true
migrate_timeout = 300
maintenance_mode = true
maintenance_mode_phases = ["migrate"]  # Valid: "drain", "migrate"
backups = true
rollback = false
search_replace = true

# Worker draining
drain_workers = false
drain_workers_timeout = 300
skip_stale_workers = true
skip_stale_timeout = 15
worker_kill_timeout = 15

# Frappe Cloud integration
[fc]
api_key = "fc_xxx"
api_secret = "fc_xxx"
site_name = "mysite.frappe.cloud"
team_name = "my-team"

# Remote worker
[remote_worker]
server_ip = "192.168.1.100"
ssh_user = "frappe"
ssh_port = 22
```

See [`example-config.toml`](example-config.toml) for complete schema with all hooks and options.

## Deploy Modes

| Mode | Use Case | Build Location | Deploy Target |
|------|----------|----------------|---------------|
| **pull** | Standard deploy | On-server | Same server |
| **ship** | Remote deploy | Local machine | Remote server via SSH/rsync |
| **bake** | CI/CD pre-build | CI runner | Tarball artifact → ship to prod |
| **publish** | Future: Registry push | CI runner | Image registry |

## Directory Structure

```
~/frappe/sites/<site>/
├── workspace/
│   ├── frappe-bench → release_YYYYMMDD_HHMMSS  (symlink to current)
│   ├── deployment-data/        (persistent across releases)
│   │   ├── sites/              (DB, files)
│   │   ├── config/             (supervisor configs)
│   │   └── logs/
│   ├── release_YYYYMMDD_HHMMSS/  (each release is isolated)
│   │   ├── apps/
│   │   ├── env/                (release-scoped Python venv)
│   │   ├── .uv/                (UV package cache, per-release)
│   │   ├── .fnm/               (Node.js runtime, per-release)
│   │   ├── sites → ../deployment-data/sites  (symlink)
│   │   └── .fmd.toml           (config snapshot)
│   └── .cache/                 (workspace-level caches)
└── deployment-backup/
    └── release_YYYYMMDD_HHMMSS/
```

## Maintenance Mode

- **Bypass tokens**: `fmd maintenance enable <site>` generates a cookie for dev access during maintenance
- **Phase control**: Enable maintenance only during `"migrate"` or `"drain"` phases, not full deploy
- **Nginx integration**: Serves custom page, honors bypass cookie

## Remote Workers

```bash
# Enable remote worker (opens Redis/MariaDB ports in docker-compose)
fmd remote-worker enable <site> --rw-server 192.168.1.100 --force

# Sync release to remote worker
fmd remote-worker sync <site> --rw-server 192.168.1.100
```

## Frappe Cloud Integration

Sync apps, Python deps, or DB backups from Frappe Cloud:

```toml
[release]
use_fc_apps = true   # FC commit hashes override local refs (preserves hooks/symlinks)
use_fc_deps = true   # Auto-set python_version from FC

[switch]
use_fc_db = true     # Download and restore latest FC backup at switch time

[fc]
api_key = "fc_xxx"
api_secret = "fc_xxx"
site_name = "mysite.frappe.cloud"
team_name = "my-team"
```

**Merge behavior**: FC apps are merged with local `[[apps]]` by repo name; FC commit hash overrides local ref, but local hooks/symlink/subdir settings are preserved. Local-only apps are kept.

## CI/CD Workflow

```bash
# 1. On CI runner: build release artifact
fmd release create --config prod.toml --mode image --build-dir /tmp/releases
cd /tmp/releases && tar -czf release.tar.gz release_*

# 2. Ship to production server
scp release.tar.gz prod:/tmp/
ssh prod "cd /path/to/workspace && tar -xzf /tmp/release.tar.gz"

# 3. Activate release on prod
ssh prod "fmd release switch --config prod.toml release_20250410_120000"
```

**Alternative**: Use `fmd deploy ship --config site.toml` for automated build-local/deploy-remote.

## Troubleshooting

**Private repo access**:
```bash
# Set GitHub token in config or environment
export GITHUB_TOKEN=ghp_xxx
fmd deploy pull --config site.toml
```

**Symlink app not found**:
```toml
[[apps]]
repo = "my-org/monorepo"
ref = "main"
subdir_path = "apps/my-app"  # Path within repo
symlink = true               # Symlink instead of copy
```

**FC integration fails**: Verify API credentials with `curl -u fc_key:fc_secret https://frappecloud.com/api/method/press.api.bench.apps`

**Worker drain timeout**: Increase timeouts if workers process long jobs:
```toml
[switch]
drain_workers_timeout = 600  # Wait 10 min for workers to finish
worker_kill_timeout = 30     # Force-kill after 30s if still running
```

**Verbose logs**:
```bash
fmd -v deploy pull <site>  # Global -v flag before subcommand
```

See [`docs/troubleshooting.md`](docs/troubleshooting.md) for more.

## Documentation

- **[Configuration Reference](example-config.toml)** — Complete config schema with comments
- **[Concepts](docs/concepts.md)** — Release lifecycle, modes, directory structure
- **[Architecture](docs/architecture.md)** — Runner system, mixins, hook lifecycle
- **[Commands](docs/commands.md)** — Detailed command reference
- **[Troubleshooting](docs/troubleshooting.md)** — Common issues and solutions

## License

MIT
