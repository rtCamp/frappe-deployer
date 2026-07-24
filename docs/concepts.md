# Concepts

fmd (Frappe Manager Deployer) adds zero-downtime deployments to an existing Frappe
Manager (FM) bench. Every deploy builds a new **immutable, timestamped release** and
repoints a **symlink** atomically. Old releases stay on disk for instant **rollback**, and
persistent state (DB, site files, configs, logs) lives once in `deployment-data/` and is
symlinked into every release — so releases share data without duplicating it.

## Atomic releases & symlink switching

A release is a self-contained bench directory named `release_YYYYMMDD_HHMMSS`. It holds
its own app source, Python venv, and Node runtime, so releases never share build
artifacts and cannot interfere with each other.

The live bench is the symlink `workspace/frappe-bench`. Activating a release is a single
atomic relink of that symlink to the target release directory. Because FM always looks at
`frappe-bench`, switching is instantaneous and reversible:

- Switch forward = point `frappe-bench` at a new release.
- Roll back = point `frappe-bench` at an older release.

You never edit these symlinks by hand; fmd manages them during `configure` and `switch`.

## Release lifecycle

A full deploy is three phases. `fmd deploy pull` runs all three in sequence; you can also
run each `release` subcommand on its own.

| Phase | Command | What it does |
|---|---|---|
| **configure** | `fmd release configure` | One-time. Converts a plain FM bench into the fmd release layout: creates `deployment-data/` (persistent state), sets up the `frappe-bench` symlink, and prepares `deployment-backup/`. Idempotent — skipped if already configured. |
| **create** | `fmd release create` | Builds a new `release_YYYYMMDD_HHMMSS/`: clones apps at their pinned refs, creates the release-scoped venv, installs Node, runs `bench build`, and runs build hooks. **Does not touch the live symlink** — safe to run while the site serves traffic. |
| **switch** | `fmd release switch <release>` | Atomically activates a release: optionally drains workers and backs up the DB, enables maintenance mode for the configured phases, relinks `frappe-bench`, runs `bench migrate`, restarts services, then disables maintenance. |

Behavior in each phase is driven by config: `[release]` governs `create`, `[switch]`
governs `switch`. See [Configuration](configuration.md).

## Workspace layout

Verified on-disk layout for a configured site:

```
~/frappe/sites/<site>/workspace/
  frappe-bench -> release_YYYYMMDD_HHMMSS      # symlink to the ACTIVE release
  deployment-data/                             # persistent across releases
    sites/   config/   logs/
  release_YYYYMMDD_HHMMSS/                      # one immutable release
    apps/  env/ (venv)  .uv/  .fnm/  sites -> ../deployment-data/sites   <site>.toml (snapshot)
  .cache/
~/frappe/sites/<site>/deployment-backup/
  release_YYYYMMDD_HHMMSS/                      # pre-switch DB + config backups
```

- **`frappe-bench`** — symlink to the active release.
- **`release_YYYYMMDD_HHMMSS/`** — one immutable release. `apps/` holds app source,
  `env/` is the release-scoped venv, `.uv/` and `.fnm/` are per-release Python/Node
  caches, `sites` symlinks back to shared data, and `<site>.toml` is a snapshot of the
  config used to build the release.
- **`deployment-data/`** — persistent state shared by every release (see below).
- **`.cache/`** — workspace-level caches reused across builds.
- **`deployment-backup/`** — pre-switch DB and config backups, one directory per release.

## Persistent data vs releases

Releases are disposable; data is not. Everything durable lives once under
`deployment-data/`:

- `sites/` — site DB config, uploaded files, and per-site data.
- `config/` — service/supervisor configuration.
- `logs/` — application logs.

Each release's `sites` entry is a symlink to `deployment-data/sites`, so all releases read
and write the same site data. Building or deleting a release never changes the DB or
uploaded files — only the code and runtimes change between releases.

## Rollback & retention

Rollback is just a switch to an older release. Because the previous release is still on
disk, reverting is as fast as any switch:

```bash
fmd release list <site>                 # see available releases
fmd release switch <site> <older_release>
```

**Automatic rollback** — with `[switch] rollback = true`, if the migration step fails
during a switch, fmd reverts `frappe-bench` to the previous working release. With
`rollback = false` (default) a failed switch leaves the site on the previous release while
preserving the new release for debugging.

**Pre-switch backups** — with `[switch] backups = true`, fmd backs up the DB and site
configs into `deployment-backup/release_YYYYMMDD_HHMMSS/` before migrating, giving a
restore point independent of the release directories.

**Retention** — `[release] releases_retain_limit` (default `7`) caps how many releases are
kept. `fmd cleanup` prunes old releases and their backups:

```bash
fmd cleanup <site> -r 3 -b 5 -y         # keep 3 releases, 5 backups
```

## Configuration precedence

Settings resolve highest-to-lowest:

1. **CLI flags** — e.g. `--app`, `--mode`.
2. **Config file** — values in `site.toml` (via `--config` or an auto-discovered file).
3. **Built-in defaults** — from fmd's config models.

`bench_name` defaults to `site_name` when unset. For the full set of sections, keys, and
defaults, see [Configuration](configuration.md); for how the build/switch runs on-server
vs. locally, see [Deploy modes](deploy-modes.md).
