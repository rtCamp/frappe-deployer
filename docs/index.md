---
hide:
  - navigation
  - toc
---

# Frappe Manager Deployer

<div class="grid cards" markdown>

-   :lucide-rocket:{ .lg .middle } &nbsp; **[Deploy in minutes](getting-started/quick-start.md)**

    ---

    Zero-downtime Frappe deployments with atomic releases, instant rollback, and automatic migrations. One command from development to production.

-   :lucide-git-branch:{ .lg .middle } &nbsp; **[Atomic releases](guides/deploy-modes.md)**

    ---

    Every deployment creates a timestamped release. Switch instantly via symlinks. Keep N previous releases for instant rollback on failure.

-   :lucide-github:{ .lg .middle } &nbsp; **[CI/CD ready](guides/github-actions.md)**

    ---

    Deploy automatically on push with GitHub Actions. Two strategies: pull (build on server) or ship (build in CI, rsync to remote).

-   :lucide-cloud:{ .lg .middle } &nbsp; **[Frappe Cloud sync](guides/frappe-cloud.md)**

    ---

    Import app list, Python dependencies, and database backups directly from Frappe Cloud. Perfect for cloud-to-self-hosted migration.

-   :lucide-zap:{ .lg .middle } &nbsp; **[Smart worker handling](guides/maintenance-mode.md)**

    ---

    Workers drain gracefully before release switch. Maintenance mode only during migrations. Skip stale workers automatically.

-   :lucide-folder-tree:{ .lg .middle } &nbsp; **[Monorepo support](guides/monorepo-apps.md)**

    ---

    Symlink subdirectory apps for efficient workspace management. Perfect for multi-app repositories with shared dependencies.

</div>

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

## Deploy your first site

```bash
fmd deploy pull site.localhost \
  --app frappe/frappe:version-15 \
  --app frappe/erpnext:version-15 \
  --maintenance-mode --backups
```

Your site deploys atomically — rollback instantly if anything fails.

!!! tip "Use a config file"
    ```bash
    # Create site.toml with your app list and settings
    fmd deploy pull --config site.toml
    ```

## Where to go next

<div class="grid" markdown>

!!! info "New to fmd?"

    Start with [Requirements](getting-started/requirements.md), then follow the [Installation guide](getting-started/installation.md) and [Quick Start](getting-started/quick-start.md).

!!! example "Ready to deploy?"

    Head to the [Guides](guides/index.md) to learn about deploy modes, GitHub Actions, hooks, Frappe Cloud sync, and more.

</div>
