# Command Reference

Complete reference for all `fmd` CLI commands. Each command page includes usage, options, and real-world examples.

---

## Quick Start

The most common commands to get you started:

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **[Deploy](deploy.md)**

    ---

    ```bash
    fmd deploy pull --config site.toml
    fmd deploy ship --config site.toml
    ```

-   :material-source-branch:{ .lg .middle } **[Release Management](release.md)**

    ---

    ```bash
    fmd release configure mysite.localhost
    fmd release create mysite.localhost
    fmd release switch mysite.localhost release_YYYYMMDD_HHMMSS
    ```

-   :material-information:{ .lg .middle } **[Info](info.md)**

    ---

    ```bash
    fmd info mysite.localhost
    fmd release list mysite.localhost
    ```

-   :material-delete:{ .lg .middle } **[Cleanup](cleanup.md)**

    ---

    ```bash
    fmd cleanup mysite.localhost -r 3 -b 5 -y
    ```

</div>

---

## Deploy Commands

Full automated deployment workflows.

### :material-rocket-launch: [`fmd deploy`](deploy.md) {.command-heading}

**Full automated deployment: configure → create → switch**

Two deployment strategies:

- **[`fmd deploy pull`](deploy-pull.md)** — Build on production server, deploy locally
- **[`fmd deploy ship`](deploy-ship.md)** — Build locally/CI, ship to remote server

```bash
fmd deploy pull --config site.toml
fmd deploy ship --config site.toml
```

---

## Release Commands

Manual control over release lifecycle for advanced workflows.

### :material-cog: [`fmd release configure`](release-configure.md) {.command-heading}

**One-time workspace setup**

Converts a plain Frappe Manager bench into a versioned release structure.

```bash
fmd release configure mysite.localhost
```

### :material-plus-circle: [`fmd release create`](release-create.md) {.command-heading}

**Build a new release**

Creates a new timestamped release without activating it. Safe operation — no changes to live site.

```bash
fmd release create mysite.localhost
fmd release create --config site.toml
```

### :material-swap-horizontal: [`fmd release switch`](release-switch.md) {.command-heading}

**Activate a release**

Atomically switch to a specific release. This is where migrations run and the site goes live with new code.

```bash
fmd release switch mysite.localhost release_20260416_143022
```

### :material-format-list-bulleted: [`fmd release list`](release-list.md) {.command-heading}

**Show all releases**

List all releases for a site with timestamps and status.

```bash
fmd release list mysite.localhost
```

---

## Site Management

### :material-information: [`fmd info`](info.md) {.command-heading}

**Show site details**

Display current release, installed apps, configuration, and deployment status.

```bash
fmd info mysite.localhost
```

### :material-delete: [`fmd cleanup`](cleanup.md) {.command-heading}

**Clean up old releases and backups**

Remove old releases and backups to free disk space.

```bash
fmd cleanup mysite.localhost -r 3 -b 5 -y
```

---

## Utilities

### :material-find-replace: [`fmd search-replace`](search-replace.md) {.command-heading}

**Search and replace in database**

Bulk find-and-replace operations across site database. Useful for domain changes.

```bash
fmd search-replace mysite.localhost "old.com" "new.com" --dry-run
```

### :material-shield-alert: [`fmd maintenance`](maintenance.md) {.command-heading}

**Manage maintenance mode**

Enable/disable maintenance mode and generate bypass tokens.

```bash
fmd maintenance enable mysite.localhost
fmd maintenance disable mysite.localhost
```

### :material-server-network: [`fmd remote-worker`](remote-worker.md) {.command-heading}

**Manage remote workers**

Configure and sync releases to remote worker servers.

```bash
fmd remote-worker enable mysite.localhost --rw-server 192.168.1.100
fmd remote-worker sync mysite.localhost --rw-server 192.168.1.100
```

---

!!! tip "Quick Help"
    Use `fmd <command> --help` to see detailed options and examples for any command.

!!! info "Global Options"
    - `fmd -v <command>` — Enable verbose logging (must precede subcommand)
    - `-c, --config <path>` — Load TOML config file (accepted by all commands)
