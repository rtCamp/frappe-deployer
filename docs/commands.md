# Command Reference

Complete reference for all fmd commands.

**Global option**: `fmd -v <command>` enables verbose logging (must precede subcommand).

**Config option**: All commands accept `--config / -c <path>` to load a TOML config file.

---

## Deploy Commands

### `fmd deploy pull`

Full automated deployment: configure (if needed) → create release → switch.

**Synopsis**:
```bash
fmd deploy pull [OPTIONS] [BENCH_NAME]
```

**Options**:
- `-c, --config <path>` — TOML config file
- `--app / -a <spec>` — App to deploy (format: `org/repo:ref` or `org/repo:ref:subdir`)
- `--maintenance-mode` — Enable maintenance mode during switch
- `--no-maintenance-mode` — Disable maintenance mode
- `--backups` — Take DB backup before switch
- `--no-backups` — Skip DB backup
- `--rollback` — Auto-rollback on failure
- `--no-rollback` — Don't auto-rollback
- `--python-version <ver>` — Python version (e.g., `3.11`)
- `--github-token <token>` — GitHub token for private repos
- `--fc-key`, `--fc-secret`, `--fc-site`, `--fc-team` — Frappe Cloud credentials
- `--fc-use-apps` — Import app list from FC
- `--fc-use-deps` — Import python_version from FC
- `--fc-use-db` — Download and restore FC backup at switch time

**Examples**:
```bash
# Minimal (uses config file)
fmd deploy pull --config site.toml

# With bench name (no config)
fmd deploy pull site.localhost

# Full with overrides
fmd deploy pull site.localhost \
  --app frappe/frappe:version-15 \
  --app frappe/erpnext:version-15 \
  --maintenance-mode --backups --rollback

# Monorepo subdirectory app
fmd deploy pull --config site.toml \
  --app my-org/monorepo:main:apps/my-app

# With Frappe Cloud integration
fmd deploy pull --config site.toml \
  --fc-key <key> --fc-secret <secret> --fc-site mysite.frappe.cloud \
  --fc-use-apps --fc-use-deps --fc-use-db
```

**Workflow**:
1. Check if workspace is configured; if not, run `release configure`
2. Create new release with `release create`
3. Switch to new release with `release switch`

---

### `fmd deploy ship`

Build release locally → rsync to remote server → switch on remote.

**Synopsis**:
```bash
fmd deploy ship --config <path> [OPTIONS]
```

**Important**: `--config` is **required** for ship mode (must specify `[ship]` section).

**Options**:
- `-c, --config <path>` — TOML config file (required)
- `--app / -a <spec>` — App to deploy
- `--maintenance-mode` — Enable maintenance mode on remote
- `--backups` — Take DB backup on remote before switch
- All other options from `deploy pull`

**Config required**:
```toml
[ship]
server_ip = "192.168.1.100"     # Remote server
ssh_user = "frappe"             # SSH username
ssh_port = 22                   # SSH port
remote_workspace_root = "/home/frappe/frappe/sites/site.localhost/workspace"
```

**Example**:
```bash
fmd deploy ship --config site.toml --app frappe/frappe:version-15
```

**Workflow**:
1. Build release locally using Docker (bake mode: no FM services needed)
2. rsync release directory to remote server
3. SSH to remote, run `fmd release switch` to activate
4. Run post-switch hooks on remote

---

## Release Commands

Low-level primitives for manual release management and CI/CD pipelines.

### `fmd release configure`

One-time workspace setup. Converts a plain bench into a versioned release structure.

**Synopsis**:
```bash
fmd release configure [OPTIONS] [BENCH_NAME]
```

**Options**:
- `-c, --config <path>` — TOML config file
- `--app / -a <spec>` — Initial apps to configure
- `--backups` — Enable backups by default

**Example**:
```bash
fmd release configure site.localhost
fmd release configure --config site.toml
```

**What it creates**:
- `deployment-data/` — Persistent data directory
  - `sites/` — Site DB and files
  - `config/` — Supervisor configs
  - `logs/` — Application logs
- `deployment-backup/` — Backup storage
- `release_YYYYMMDD_HHMMSS/` — First release directory

**Next step**: Run `fmd release create` to build a new release, or `fmd deploy pull` for automated deploy.

---

### `fmd release create`

Create a new release without affecting the live bench.

**Synopsis**:
```bash
fmd release create [OPTIONS] [BENCH_NAME]
```

**Options**:
- `-c, --config <path>` — TOML config file
- `--app / -a <spec>` — Apps to include
- `--python-version <ver>` — Python version
- `--node-version <ver>` — Node.js version
- `--mode <exec|image>` — Runner mode (default: exec)
- `--build-dir <path>` — Output directory for image mode (forces image mode)
- `--runner-image <image>` — Docker image for image mode

**Modes**:

- **exec** (default): Build using Frappe Manager's running docker-compose services. Fast, requires FM site to be running.
- **image**: Build in a fresh Docker container. Slower, but works without FM running. Required for CI/CD.

**Examples**:
```bash
# Standard create (uses running FM services)
fmd release create site.localhost

# With config file
fmd release create --config site.toml

# CI/CD mode: build in isolated container
fmd release create --mode image --build-dir /tmp/releases
# Output: /tmp/releases/release_YYYYMMDD_HHMMSS/

# Use custom Docker image
fmd release create --mode image --runner-image ghcr.io/my-org/fm-builder:latest
```

**What it does**:
1. Clone app repositories (or update if symlinked)
2. Create Python venv with release-scoped `.uv/` cache
3. Install Python dependencies
4. Install Node.js in release-scoped `.fnm/`
5. Run `bench build` for frontend assets
6. Execute pre/post-build hooks

**Safe**: Does not touch `frappe-bench` symlink. Can run while site is live.

---

### `fmd release switch`

Atomically activate a previously-created release.

**Synopsis**:
```bash
fmd release switch [OPTIONS] BENCH_NAME RELEASE_NAME
```

**Arguments**:
- `BENCH_NAME` — Bench/site name
- `RELEASE_NAME` — Release directory name (e.g., `release_20250410_120000`)

**Options**:
- `-c, --config <path>` — TOML config file
- `--maintenance-mode` — Enable maintenance mode during switch
- `--backups` — Take DB backup before switch
- `--rollback` — Auto-rollback on failure
- `--migrate / --no-migrate` — Run bench migrate (default: yes)
- `--search-replace / --no-search-replace` — Run DB search-replace (default: yes)

**Examples**:
```bash
# Minimal
fmd release switch site.localhost release_20250410_120000

# With safety features
fmd release switch site.localhost release_20250410_120000 \
  --maintenance-mode --backups --rollback

# Rollback to previous release
fmd release switch site.localhost release_20250409_100000
```

**Workflow**:
1. Validate release exists and is ready
2. Drain workers (if `drain_workers = true`)
3. Take DB backup (if `backups = true`)
4. Enable maintenance mode (during configured phases only)
5. Update `frappe-bench` symlink → `release_YYYYMMDD_HHMMSS/` (atomic)
6. Patch `common_site_config.json` and `site_config.json` (if configured)
7. Run `bench migrate`
8. Restart services (fmx restart)
9. Disable maintenance mode
10. Sync to remote workers (if `sync_workers = true`)

**Downtime**: Typically <30s (migrate + restart only). Symlink switch is instant.

---

### `fmd release list`

List all releases with current marker and metadata.

**Synopsis**:
```bash
fmd release list [OPTIONS] [BENCH_NAME]
```

**Options**:
- `-c, --config <path>` — TOML config file

**Example**:
```bash
fmd release list site.localhost
```

**Output**:
```
╭──────────────────────────────┬──────────┬────────┬──────┬──────┬──────────────────────────────────────────╮
│ Status │ Release               │ Size     │ Python │ Node │ Apps │ Symlink                                  │
├────────┼───────────────────────┼──────────┼────────┼──────┼──────┼──────────────────────────────────────────┤
│ ●      │ release_20250410_1200 │ 1.2 GB   │ 3.11   │ 18   │ 2    │ workspace/frappe-bench → (current)       │
│        │ release_20250409_1000 │ 1.1 GB   │ 3.11   │ 18   │ 2    │ workspace/frappe-bench-prev              │
│        │ release_20250408_0900 │ 1.0 GB   │ 3.10   │ 16   │ 2    │ (no symlink)                             │
╰────────┴───────────────────────┴──────────┴────────┴──────┴──────┴──────────────────────────────────────────╯
```

- **●** indicates the currently active release (symlinked via `frappe-bench`)

---

## Maintenance Commands

### `fmd cleanup`

Remove old releases and backups based on retention policy.

**Synopsis**:
```bash
fmd cleanup [OPTIONS] [BENCH_NAME]
```

**Options**:
- `-c, --config <path>` — TOML config file
- `-r, --release-retain-limit <n>` — Keep last N releases (default: 7)
- `-b, --backup-retain-limit <n>` — Keep last N backups (default: same as releases)
- `--show-sizes` — Display disk usage for each item
- `-y, --yes` — Skip confirmation prompt

**Examples**:
```bash
# Interactive (prompts for confirmation)
fmd cleanup site.localhost

# Auto-confirm, keep 3 releases and 5 backups
fmd cleanup site.localhost -r 3 -b 5 -y

# Show sizes before deleting
fmd cleanup --config site.toml --show-sizes
```

**Workflow**:
1. List all releases and backups
2. Mark oldest items for deletion (beyond retention limit)
3. Show what will be deleted (with sizes if `--show-sizes`)
4. Prompt for confirmation (unless `-y`)
5. Delete marked items

**Safety**: Never deletes the currently active release (marked with ●).

---

### `fmd search-replace`

Find and replace text across all text fields in the Frappe database.

**Synopsis**:
```bash
fmd search-replace [OPTIONS] BENCH_NAME SEARCH REPLACE
```

**Arguments**:
- `BENCH_NAME` — Bench/site name
- `SEARCH` — Text to find
- `REPLACE` — Replacement text

**Options**:
- `-c, --config <path>` — TOML config file
- `--dry-run` — Show what would be replaced without making changes

**Examples**:
```bash
# Dry run (preview changes)
fmd search-replace site.localhost "old.domain.com" "new.domain.com" --dry-run

# Execute replacement
fmd search-replace site.localhost "old.domain.com" "new.domain.com"

# Using config file
fmd search-replace --config site.toml "old-text" "new-text"
```

**Use cases**:
- Domain migration: Change all URLs after moving to a new domain
- Text corrections: Fix typos in DB content
- Configuration updates: Update hardcoded values across the DB

**Limitations**: Only works in **FM mode** (uses `bench --site all search-replace` internally).

---

### `fmd info`

Show git state for each installed app.

**Synopsis**:
```bash
fmd info [OPTIONS] [BENCH_NAME]
```

**Options**:
- `-c, --config <path>` — TOML config file

**Example**:
```bash
fmd info site.localhost
```

**Output**:
```toml
[[apps]]
app_name = "frappe"
repo = "frappe/frappe"
ref = "a1b2c3d4e5"  # Commit hash
branch = "version-15"
tag = ""
latest_commit = "fix: resolve caching issue in background jobs"

[[apps]]
app_name = "erpnext"
repo = "frappe/erpnext"
ref = "f9e8d7c6b5"
branch = "version-15"
tag = "v15.1.0"
latest_commit = "feat: add support for multi-currency invoices"
```

---

## Remote Worker Commands

### `fmd remote-worker enable`

Enable remote worker mode by opening database and cache ports in docker-compose.

**Synopsis**:
```bash
fmd remote-worker enable [OPTIONS] BENCH_NAME
```

**Options**:
- `-c, --config <path>` — TOML config file
- `--rw-server <ip>` — Remote worker server IP
- `--rw-user <user>` — SSH username for remote (default: frappe)
- `--force` — Skip confirmation prompts

**Example**:
```bash
fmd remote-worker enable site.localhost --rw-server 192.168.1.100 --force
```

**What it does**:
1. Scans for available ports:
   - **Redis**: 11000+
   - **MariaDB**: 3306+ (finds first free port)
2. Updates `docker-compose.override.yml` to expose ports:
   ```yaml
   services:
     mariadb:
       ports:
         - "3307:3306"
     redis-cache:
       ports:
         - "11000:6379"
     redis-queue:
       ports:
         - "11001:6379"
   ```
3. Writes connection details to `workspace/.remote-worker-config.json`
4. Restarts docker-compose services

**Network requirements**:
- Firewall must allow connections on the exposed ports
- Remote worker must be able to reach primary server IP

---

### `fmd remote-worker sync`

Rsync release directory to remote worker server.

**Synopsis**:
```bash
fmd remote-worker sync [OPTIONS] BENCH_NAME
```

**Options**:
- `-c, --config <path>` — TOML config file
- `--rw-server <ip>` — Remote worker server IP
- `--rw-user <user>` — SSH username (default: frappe)

**Example**:
```bash
fmd remote-worker sync site.localhost --rw-server 192.168.1.100
```

**What gets synced**:
- `apps/` — Application code
- `env/` — Python virtual environment
- `.uv/`, `.fnm/` — Runtime caches
- Config files

**Excluded** (uses remote server's own):
- `sites/` — Remote has its own DB/files
- `public/` — Generated on remote
- `private/` — Site-specific files
- `.git/`, `node_modules/`, `__pycache__/`

**Workflow**:
1. Read `.remote-worker-config.json` for remote connection details
2. rsync current release directory to remote server
3. SSH to remote and restart services

**Performance**: First sync is slow (full copy). Subsequent syncs are incremental (fast).

---

## Global Options

All commands accept:

- `--config / -c <path>` — TOML config file (alternative to positional BENCH_NAME)
- `-v / --verbose` — Enable verbose logging (must precede subcommand: `fmd -v deploy pull`)

**Config priority**:
1. CLI arguments (highest)
2. Environment variables
3. TOML config file
4. Built-in defaults (lowest)

**Exit codes**:
- `0` — Success
- `1` — Error (logged to stderr)
- `2` — Validation error (invalid arguments or config)
