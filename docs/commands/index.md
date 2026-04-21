# Commands

Complete reference for all `fmd` CLI commands.

!!! tip "Command help"
    Use `fmd <command> --help` to see detailed options and examples for any command.

!!! info "Global options"
    - `fmd -v <command>` — Enable verbose logging (must precede subcommand)
    - `-c, --config <path>` — Load TOML config file (accepted by all commands)

---

## Quick Overview

<div class="grid cards" markdown>

-   :lucide-rocket:{ .lg .middle } **[Deploy](deploy.md)**

    ---

    Full automated deployment workflows: configure → create → switch

    ```bash
    fmd deploy pull --config site.toml
    fmd deploy ship --config site.toml
    ```

-   :lucide-git-branch:{ .lg .middle } **[Release Management](release.md)**

    ---

    Manual control over release lifecycle for advanced workflows

    ```bash
    fmd release configure mysite.localhost
    fmd release create mysite.localhost
    fmd release switch mysite.localhost release_YYYYMMDD_HHMMSS
    ```

-   :lucide-users:{ .lg .middle } **[Remote Workers](remote-worker.md)**

    ---

    Configure and sync releases to remote worker servers

    ```bash
    fmd remote-worker enable mysite.localhost --rw-server 192.168.1.100
    fmd remote-worker sync mysite.localhost --rw-server 192.168.1.100
    ```

-   :lucide-trash-2:{ .lg .middle } **[Cleanup](cleanup.md)**

    ---

    Clean up old releases and backups to free disk space

    ```bash
    fmd cleanup mysite.localhost -r 3 -b 5 -y
    ```

</div>

---

## All Commands

Detailed documentation for each command is auto-generated from the CLI. Click the links above or navigate using the sidebar.
