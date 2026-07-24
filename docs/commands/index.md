# Commands

Overview of the `fmd` CLI. Per-command detail pages are auto-generated from the CLI by
`scripts/update_cli_docs.py`; for authoritative, up-to-date options run
`fmd <command> --help`.

!!! info "Global options"
    - `fmd -v <command>` — verbose logging (the `-v/--verbose` flag must precede the subcommand)
    - `-V, --version` — print the version
    - `-c, --config <path>` — load a TOML config file (accepted by every command)

    Commands take either a positional `<site>`/bench name or `--config site.toml`.

---

## Command tree

<div class="grid cards" markdown>

-   :lucide-rocket:{ .lg .middle } **Deploy**

    ---

    End-to-end deployment workflows.

    - `deploy pull` — configure (if needed) → create → switch on the target server
    - `deploy ship` — build locally/CI → rsync → configure + switch on the remote

    ```bash
    fmd deploy pull --config site.toml
    fmd deploy ship --config site.toml
    ```

-   :lucide-git-branch:{ .lg .middle } **Release**

    ---

    Manual control over the release lifecycle.

    - `release configure` — convert an FM bench to the fmd release layout (one-time)
    - `release create` — build a release without changing the live site
    - `release switch` — atomically activate a release
    - `release list` — list releases
    - `release shell` — interactive shell inside a release's build container
    - `release info` — inspect each app's git repo/branch/commit/tag

    ```bash
    fmd release create mysite.localhost
    fmd release switch mysite.localhost release_YYYYMMDD_HHMMSS
    fmd release info mysite.localhost
    ```

-   :lucide-users:{ .lg .middle } **Remote worker**

    ---

    Run workers on separate servers.

    - `remote-worker enable` — open Redis/MariaDB ports for remote workers
    - `remote-worker sync` — sync the active release to a remote worker

    ```bash
    fmd remote-worker enable mysite.localhost --rw-server 192.168.1.100
    fmd remote-worker sync mysite.localhost --rw-server 192.168.1.100
    ```

-   :lucide-replace:{ .lg .middle } **Search / replace**

    ---

    DB-wide string replace, e.g. rewrite a site URL.

    ```bash
    fmd search-replace mysite.localhost old.com new.com --dry-run
    fmd search-replace mysite.localhost old.com new.com
    ```

-   :lucide-trash-2:{ .lg .middle } **Cleanup**

    ---

    Remove old releases and backups to free disk space.

    ```bash
    fmd cleanup mysite.localhost -r 3 -b 5 -y --show-sizes
    ```

</div>

---

See [Concepts](../concepts.md) for the release model and [Configuration](../configuration.md)
for the TOML options each command reads.
