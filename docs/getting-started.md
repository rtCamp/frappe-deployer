# Getting started

fmd (Frappe Manager Deployer) layers zero-downtime, release-based deploys on top of an
existing Frappe Manager (FM) bench. This page covers requirements, installation, and your
first deployment.

## Requirements

- **Python >=3.13,<3.14**
- **Docker** with **Compose v2** (the `docker compose` command, not the legacy `docker-compose`)
- **Frappe Manager**, with an existing FM bench for the site you will deploy

Verify:

```bash
python3 --version
docker compose version
fm --version
```

If you don't have an FM bench yet, create one first:

```bash
fm create mysite --environment prod   # bench at ~/frappe/sites/mysite/
```

## Install

=== "uv (recommended)"

    ```bash
    uv tool install frappe-deployer
    ```

=== "pipx"

    ```bash
    pipx install frappe-deployer
    ```

=== "From source"

    ```bash
    git clone https://github.com/rtcamp/fmd.git
    cd fmd
    pip install -e .
    ```

Verify:

```bash
fmd --version
```

!!! tip "GitHub token for private repos"
    To clone private app repositories (and avoid API rate limits), provide a GitHub token
    via the `GITHUB_TOKEN` environment variable or the `github_token` key in your config file:

    ```bash
    export GITHUB_TOKEN=ghp_your_token_here
    ```

## Quick start

### 1. Configure the release layout (one-time)

Convert your FM bench to the fmd release layout. Run this once per site:

```bash
fmd release configure mysite.localhost
```

### 2. Deploy Frappe + ERPNext

```bash
fmd deploy pull mysite.localhost \
  --app frappe/frappe:version-15 \
  --app frappe/erpnext:version-15 \
  --maintenance-mode \
  --backups
```

This builds a new timestamped release, backs up the DB, runs migrations under maintenance
mode, and switches the live symlink to the new release atomically.

### 3. Verify

```bash
fmd release list mysite.localhost   # list all releases
fmd release info mysite.localhost   # inspect each app's repo/branch/commit/tag
```

### Config-file alternative

For repeatable, version-controlled deploys, put the flags in a `site.toml`:

```toml
site_name = "mysite.localhost"
bench_name = "mysite"
github_token = "ghp_your_token"  # optional, for private repos

[[apps]]
repo = "frappe/frappe"
ref = "version-15"

[[apps]]
repo = "frappe/erpnext"
ref = "version-15"

[switch]
maintenance_mode = true
backups = true
```

Then deploy with:

```bash
fmd deploy pull --config site.toml
```

## Next steps

- [Concepts](concepts.md) — releases, atomic symlink switch, rollback, directory layout
- [Configuration](configuration.md) — all config sections, apps, hooks, and precedence
- [Deploy modes](deploy-modes.md) — pull vs ship
