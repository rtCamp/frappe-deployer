---
hide:
  - navigation
  - toc
---

# Frappe Manager Deployer

**fmd** layers zero-downtime deployments on top of an existing Frappe Manager (FM) bench.
Every deploy builds a new immutable, timestamped release; the live bench is a symlink
repointed atomically, so switches are instant and rollback is a symlink away.

<div class="grid cards" markdown>

-   :lucide-rocket:{ .lg .middle } &nbsp; **[Get started](getting-started.md)**

    ---

    Requirements, install, and a first deploy in minutes. One command from an FM bench to a live release.

-   :lucide-git-branch:{ .lg .middle } &nbsp; **[Deploy modes](deploy-modes.md)**

    ---

    **pull** builds on the target server and switches there. **ship** builds locally or in CI, rsyncs the release, then configures and switches on the remote.

-   :lucide-github:{ .lg .middle } &nbsp; **[GitHub Actions](github-actions.md)**

    ---

    Deploy on push with the `rtcamp/frappe-deployer` composite action. One input: `command: pull` or `command: ship`.

-   :lucide-settings:{ .lg .middle } &nbsp; **[Configuration](configuration.md)**

    ---

    TOML config for apps, build hooks, Frappe Cloud sync, restore-from-site, monorepo apps, remote workers, and maintenance-as-config.

-   :lucide-book-open:{ .lg .middle } &nbsp; **[Concepts](concepts.md)**

    ---

    The mental model: releases, atomic symlink switch, shared persistent data, lifecycle, rollback, and config precedence.

-   :lucide-cloud:{ .lg .middle } &nbsp; **[Maintenance mode](configuration.md#maintenance-mode)**

    ---

    Maintenance is config-only via `[switch]`: enable it and choose which phases (e.g. `migrate`) show a maintenance page.

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

Requires Python >=3.13,<3.14, Docker + Docker Compose v2, and Frappe Manager with an
existing bench for the site.

## Deploy your first site

```bash
fmd deploy pull site.localhost \
  --app frappe/frappe:version-15 \
  --app frappe/erpnext:version-15
```

`deploy pull` configures the bench (if needed), builds a release, and switches to it
atomically — rollback instantly if anything fails.

!!! tip "Use a config file"
    ```bash
    # site.toml holds your app list and settings
    fmd deploy pull --config site.toml
    ```

## Where to go next

<div class="grid" markdown>

!!! info "New to fmd?"

    Start with [Getting Started](getting-started.md), then read [Concepts](concepts.md) to understand releases and the symlink switch.

!!! example "Ready to deploy?"

    See [Deploy modes](deploy-modes.md), [Configuration](configuration.md), and [GitHub Actions](github-actions.md).

</div>
