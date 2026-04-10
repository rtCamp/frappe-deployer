# Core Concepts

## Deploy Modes

fmd supports four deployment modes optimized for different workflows:

| Mode | Purpose | Build Location | Deploy Target | Status |
|------|---------|----------------|---------------|--------|
| **pull** | Standard deployment | On-server in docker-compose | Same server | ✅ Active |
| **ship** | Remote deployment | Local machine | Remote server via rsync | ✅ Active |
| **bake** | CI/CD artifact build | CI runner (Docker) | Tarball → ship manually | 🚧 Planned |
| **publish** | Registry deployment | CI runner | Container registry | 📋 Future |

### pull — Standard Deployment

```bash
fmd deploy pull site.localhost --app frappe/frappe:version-15
```

**Workflow**: configure (if needed) → create release → switch

**Where it runs**: Directly on the target server using Frappe Manager's docker-compose services (MariaDB, Redis running).

**Best for**: Development, staging, and production servers where you deploy directly.

### ship — Remote Deployment

```bash
fmd deploy ship --config site.toml  # Builds locally, deploys remotely
```

**Workflow**: 
1. Create release on local machine (bake mode: fresh Docker container, no live services needed)
2. rsync release directory to remote server
3. SSH to remote, run `fmd release switch` to activate

**Best for**: Deploying from a local dev machine to a remote production server.

### bake — CI/CD Artifact Build

```bash
fmd release create --mode image --build-dir /tmp/releases
# Creates release in /tmp/releases/release_YYYYMMDD_HHMMSS/
# Tar it, upload to artifact storage, download on prod, switch
```

**Where it runs**: CI runner in a clean Docker container (no Frappe Manager services required).

**Best for**: GitLab CI, GitHub Actions, Jenkins — build artifacts that can be deployed anywhere.

### publish — Container Registry (Future)

Push complete release as a Docker image to a registry, pull on target servers.

**Status**: Planned, not yet implemented.

---

## Release Lifecycle

### 1. configure (One-Time Setup)

```bash
fmd release configure site.localhost
```

Converts a plain bench directory into a versioned release structure:
- Creates `deployment-data/` for persistent files (sites, config, logs)
- Creates `deployment-backup/` for backups
- Initializes first release directory with timestamp

### 2. create (Build New Release)

```bash
fmd release create site.localhost
```

Creates a new timestamped release (`release_YYYYMMDD_HHMMSS/`):
- Clones app repositories
- Builds Python venv with release-scoped `.uv/` cache
- Installs Node.js in release-scoped `.fnm/`
- Runs `bench build` for frontend assets
- Executes pre/post-build hooks

**Safe**: Does not touch the live bench symlink. Can run while site is serving traffic.

### 3. switch (Activate Release)

```bash
fmd release switch site.localhost release_20250410_120000
```

Atomically activates a release:
- Drains workers (optional: `drain_workers = true`)
- Takes DB backup (optional: `backups = true`)
- Enables maintenance mode (during `migrate` phase only by default)
- Symlinks `workspace/frappe-bench → release_YYYYMMDD_HHMMSS/`
- Runs `bench migrate`
- Restarts services
- Disables maintenance mode

**Fast**: Typically <30s downtime (just migrate + restart). Symlink switch is atomic.

### 4. rollback

```bash
fmd release switch site.localhost release_20250409_100000  # Previous release
```

Rollback is just another switch to an older release. Previous releases are preserved based on `releases_retain_limit`.

---

## Directory Structure

```
~/frappe/sites/site.localhost/
├── workspace/
│   ├── frappe-bench → release_20250410_120000  (symlink — atomic switch)
│   │
│   ├── deployment-data/                         (persistent across releases)
│   │   ├── sites/
│   │   │   ├── common_site_config.json
│   │   │   └── site.localhost/
│   │   │       ├── site_config.json
│   │   │       ├── private/
│   │   │       └── public/
│   │   ├── config/           (supervisor configs)
│   │   ├── logs/             (application logs)
│   │   └── apps/             (symlinked app clones, organized by release)
│   │       └── release_20250410_120000/
│   │           └── erpnext_clone/  (git clone of erpnext, symlinked)
│   │
│   ├── release_20250410_120000/    (current release)
│   │   ├── apps/
│   │   │   ├── frappe/             (full clone or copy)
│   │   │   └── erpnext → ../../deployment-data/apps/.../erpnext_clone  (symlink if enabled)
│   │   ├── env/                    (Python venv)
│   │   ├── .uv/                    (UV package cache, per-release)
│   │   ├── .fnm/                   (Node.js runtime, per-release)
│   │   ├── sites → ../deployment-data/sites  (symlink)
│   │   ├── config → ../deployment-data/config
│   │   ├── logs → ../deployment-data/logs
│   │   └── .fmd.toml               (config snapshot for this release)
│   │
│   ├── release_20250409_100000/    (previous release, kept for rollback)
│   └── .cache/                     (workspace-level caches)
│
└── deployment-backup/
    ├── release_20250410_120000/
    │   └── site.localhost_20250410_120030.sql.gz  (DB backup)
    └── release_20250409_100000/
        └── site.localhost_20250409_100030.sql.gz
```

### Key Directories

- **deployment-data/**: Survives across all releases. Contains site DB, files, and configs.
- **deployment-backup/**: DB backups organized by release, with retention policy.
- **release_YYYYMMDD_HHMMSS/**: Each release is fully isolated with its own Python venv, Node.js runtime, and app code.
- **frappe-bench symlink**: Points to current active release. Switched atomically during deploy.

### Runtime Isolation

Each release has isolated Python and Node.js runtimes:

- **`.uv/`**: UV package cache (per-release). Python packages installed here don't affect other releases.
- **`.fnm/`**: Node.js installation (per-release). Multiple releases can use different Node versions.
- **`env/`**: Python virtual environment (per-release). Different Python versions per release.

This allows:
- Test a release with Python 3.11 while production runs Python 3.10
- Different Node.js versions for frontend builds
- Instant rollback without dependency conflicts

---

## Configuration Hierarchy

Settings are merged from multiple sources (highest to lowest priority):

1. **CLI arguments** — e.g., `--app frappe/frappe:version-15 --maintenance-mode`
2. **Environment variables** — e.g., `GITHUB_TOKEN=ghp_xxx`
3. **TOML config file** — `site.toml` loaded via `--config` or auto-discovered
4. **Default values** — Built-in defaults from Pydantic models

Example:
```bash
# Config file says: maintenance_mode = false
# CLI override: --maintenance-mode
# Result: maintenance enabled (CLI wins)
fmd deploy pull --config site.toml --maintenance-mode
```

---

## App Management

### Repository Format

Apps are specified as `org/repo:ref` or `org/repo:ref:subdir_path`:

```toml
[[apps]]
repo = "frappe/frappe"
ref = "version-15"  # Branch, tag, or commit hash

[[apps]]
repo = "my-org/monorepo"
ref = "main"
subdir_path = "apps/custom-app"  # For monorepos
symlink = true                   # Symlink instead of copy
```

### Build Process

During `release create`:

1. **Clone**: `git clone https://github.com/org/repo` (or use GitHub token for private)
2. **Checkout**: `git checkout ref`
3. **Subdir**: If `subdir_path` set, use that directory (monorepo support)
4. **Symlink**: If `symlink = true`, symlink to `deployment-data/apps/<release>/<app>_clone/`
5. **Hooks**: Run `before_python_install` → `pip install` → `after_python_install`
6. **Build**: Run `before_bench_build` → `bench build` → `after_bench_build`
7. **Migrate**: (During switch phase) `bench migrate`

### Symlink vs Copy

**Copy** (default):
- App code is duplicated in each release
- Slower clones, more disk space
- Safer: each release is fully independent

**Symlink** (`symlink = true`):
- App code is cloned once to `deployment-data/apps/<release>/<app>_clone/`
- Each release symlinks to the same clone
- Faster deploys, less disk space
- **Recommended for monorepo subdirectory apps**

---

## Backup Strategy

### Automatic Backups

Before each `release switch` (if `backups = true`):

1. **Database dump**: `bench --site <site> backup --with-files` (compressed `.sql.gz`)
2. **Storage**: Saved to `deployment-backup/release_YYYYMMDD_HHMMSS/`
3. **Retention**: Keeps last N backups based on `releases_retain_limit`

### Retention Policy

```toml
[release]
releases_retain_limit = 7  # Keep last 7 releases + their backups
```

When exceeded, `fmd cleanup` removes:
- Oldest release directories
- Corresponding backup directories

Manual cleanup:
```bash
fmd cleanup site.localhost --release-retain-limit 3 --backup-retain-limit 5 --yes
```

---

## Maintenance Mode

### How It Works

During `release switch`, fmd enables maintenance mode to prevent user requests during migrations:

1. **Nginx config**: fmd modifies nginx config to serve a maintenance page
2. **Bypass token**: Generates a cookie for developer access during maintenance
3. **Phase control**: Enable maintenance only during specific phases (default: `["migrate"]`)

### Phase Control

```toml
[switch]
maintenance_mode = true
maintenance_mode_phases = ["migrate"]  # Valid: "drain", "migrate"
```

- **`["migrate"]`** — Maintenance only during DB migration (default)
- **`["drain", "migrate"]`** — Maintenance during worker drain + migration
- **`[]`** — Maintenance for all phases (entire switch operation)

### Bypass Token

```bash
fmd maintenance enable site.localhost
# Outputs a cookie value to paste in browser dev tools
# Access site during maintenance for testing
```

---

## Worker Draining

Gracefully stop background workers before restart:

```toml
[switch]
drain_workers = true
drain_workers_timeout = 300    # Wait up to 5 min for jobs to finish
skip_stale_workers = true      # Skip workers that haven't checked in recently
skip_stale_timeout = 15        # Worker is stale if no checkin for 15s
worker_kill_timeout = 15       # Force-kill after 15s if drain fails
```

**Drain workflow**:
1. fmd marks workers for drain (background job enqueue is disabled)
2. Waits for workers to finish current jobs (up to `drain_workers_timeout`)
3. Skips stale workers (haven't checked in for `skip_stale_timeout`)
4. Force-kills workers still running after `worker_kill_timeout`

---

## Frappe Cloud Integration

Sync app lists, Python dependencies, or database backups from Frappe Cloud:

```toml
[release]
use_fc_apps = true   # Merge FC app list with local [[apps]]
use_fc_deps = true   # Set python_version from FC dependencies

[switch]
use_fc_db = true     # Download and restore latest FC backup at switch time

[fc]
api_key = "fc_xxx"
api_secret = "fc_xxx"
site_name = "mysite.frappe.cloud"
team_name = "my-team"
```

### App Merge Behavior

When `use_fc_apps = true`, fmd:
1. Fetches app list from Frappe Cloud API
2. Merges with local `[[apps]]` by repo name (case-insensitive)
3. **FC commit hash overrides local ref** (FC always has the deployed hash)
4. **Preserves local settings**: `hooks`, `symlink`, `subdir_path` from local config
5. **Keeps local-only apps**: Apps in local config but not in FC are preserved

Example:
```toml
# Local config
[[apps]]
repo = "frappe/erpnext"
ref = "version-15"    # Branch name
symlink = true
before_bench_build = "echo 'Building ERPNext'"

# FC returns: repo="frappe/erpnext", ref="a1b2c3d4" (commit hash)
# Result: ref="a1b2c3d4" (FC commit), symlink=true, hook preserved
```

---

## Next Steps

- **[Configuration Reference](../example-config.toml)** — Complete config schema
- **[Commands](commands.md)** — Detailed command reference
- **[Architecture](architecture.md)** — Runner system and implementation details
