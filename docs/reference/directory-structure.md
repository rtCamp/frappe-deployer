# Directory Structure

Understanding the workspace and release directory layout in fmd.

## Overview

fmd organizes deployments in a structured workspace with versioned releases and persistent data separation.

```
~/frappe/sites/<site>/
├── workspace/
│   ├── frappe-bench → release_YYYYMMDD_HHMMSS  (symlink to current)
│   ├── deployment-data/        (persistent across releases)
│   │   ├── sites/              (DB, files, configs)
│   │   ├── config/             (supervisor configs)
│   │   └── logs/               (application logs)
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

## Workspace Root

The workspace is the top-level directory containing all releases and persistent data.

**Location**: `~/frappe/sites/<site>/workspace/`

Created by: `fmd release configure <site>`

### frappe-bench Symlink

```
workspace/frappe-bench → release_20260416_143022
```

The **active release** is always pointed to by this symlink. Switching releases is just updating this symlink atomically.

**Why symlinks?**

- Instant switching (atomic operation)
- Zero downtime
- Easy rollback (just point to previous release)
- Frappe Manager expects a `frappe-bench` directory

## deployment-data/

Persistent data that **survives** across releases.

```
deployment-data/
├── sites/
│   └── <site.localhost>/
│       ├── site_config.json
│       ├── private/
│       ├── public/
│       └── locks/
├── config/
│   └── supervisor.conf
└── logs/
    ├── web.log
    ├── worker.log
    └── redis.log
```

### sites/

Frappe site data:

- **site_config.json**: Site configuration (database credentials, Redis config)
- **private/**: Uploaded files (attachments, backups)
- **public/**: Public files (built assets served by nginx)
- **locks/**: Frappe locking mechanism

This directory is **symlinked** from each release:

```
release_20260416_143022/sites → ../deployment-data/sites
```

### config/

Supervisor configuration files for managing background workers.

### logs/

Application logs from all services:

- `web.log`: Gunicorn web server logs
- `worker.log`: Background worker logs
- `redis.log`: Redis logs (if local Redis)

## Release Directories

Each release is a timestamped directory: `release_YYYYMMDD_HHMMSS`

```
release_20260416_143022/
├── apps/
│   ├── frappe/
│   ├── erpnext/
│   └── ...
├── env/
│   └── (Python virtualenv)
├── .uv/
│   └── (UV cache)
├── .fnm/
│   └── (Node.js via fnm)
├── sites → ../deployment-data/sites
├── .fmd.toml
├── .build_log
└── .migrate_log
```

### apps/

Source code for all installed apps. Cloned from GitHub during build.

### env/

Python virtual environment **scoped to this release**. Each release has its own isolated dependencies.

Created by: `uv venv` during release build

### .uv/

UV package cache for faster subsequent dependency installs.

### .fnm/

Node.js runtime managed by [fnm](https://github.com/Schniz/fnm). Each release can have a different Node version.

### sites/ (symlink)

Points to `../deployment-data/sites` so all releases share the same site data.

### .fmd.toml

Snapshot of the configuration used to create this release. Useful for auditing and rollback.

### .build_log, .migrate_log

Build and migration logs for this release.

## .cache/

Workspace-level caches shared across releases:

```
.cache/
├── repos/          # Git repository clones (reused across releases)
└── pip/            # Pip download cache
```

These caches speed up subsequent builds by avoiding re-downloading dependencies.

## deployment-backup/

Backups of releases before major operations.

```
deployment-backup/
└── release_20260415_120000/
    └── (full copy of release before it was deleted/modified)
```

Created when:

- Deleting old releases beyond retention limit
- Rolling back from failed deployment
- Running `fmd cleanup`

## Example: Multiple Releases

After several deployments:

```
workspace/
├── frappe-bench → release_20260416_143022  (current)
├── deployment-data/
│   └── sites/
├── release_20260415_120000/  (old)
├── release_20260415_183045/  (old)
├── release_20260416_091532/  (previous)
├── release_20260416_143022/  (current)
└── .cache/
```

## Disk Space Usage

**Typical release size** (Frappe + ERPNext):

- Apps source: ~150 MB
- Python venv: ~300 MB
- Node modules: ~200 MB
- Built assets: ~50 MB
- **Total per release**: ~700 MB

With default retention (7 releases): **~5 GB**

Plus persistent data (sites/):

- Database: depends on usage
- Uploaded files: depends on usage
- Backups: depends on retention policy

**Recommendation**: 10+ GB free space for comfortable operation.

## Cleanup

Remove old releases to free disk space:

```bash
fmd cleanup mysite.localhost -r 3 -y
```

This keeps the 3 most recent releases and deletes the rest.

## Symlink Management

fmd manages symlinks automatically:

1. **During configure**: Creates initial `frappe-bench` symlink
2. **During switch**: Updates symlink atomically to new release
3. **During rollback**: Reverts symlink to previous release

You should **never** manually edit these symlinks.

## Monorepo Apps

Apps with `symlink = true` are symlinked instead of copied:

```
release_20260416_143022/apps/
├── frappe/         (copied)
├── erpnext/        (copied)
└── my-app → /path/to/monorepo/apps/my-app  (symlinked)
```

See [Monorepo Apps Guide](../guides/monorepo-apps.md) for details.

## Next Steps

- Understand [release lifecycle](concepts.md)
- Learn about [rollback and recovery](../guides/rollback.md)
- Configure [retention limits](../guides/configuration.md#retention-limit)
