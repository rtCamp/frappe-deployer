# Architecture

## Deployment Modes

Two user-facing deploy commands (`pull`, `ship`) built on three internal managers.

### Git-based (User-Facing)

| Mode | Build happens | Deploy happens | Transport | CLI Command |
|---|---|---|---|---|
| `pull` | Server | Server | SSH / direct | `fmd deploy pull` |
| `ship` | Runner (local/CI) | Server | rsync → DOCKER_HOST SSH | `fmd deploy ship` |

#### `pull`
Everything runs on the server. Clone apps from git, pip install, bench build, fmx restart — all in-place. Handled by `PullManager`.

#### `ship`
Runner creates a fully baked release directory locally (inside Docker containers), rsyncs it to the server, then finalizes remotely (bench symlink, fmx restart, app install) via `DOCKER_HOST=ssh://`. Server never touches git. Handled by `ShipManager(BakeManager)`.

### Image-based (Internal Managers)

| Manager | Purpose | Status |
|---|---|---|
| `BakeManager` | Build Docker images from source | ✅ exists (used internally by `ship`) |
| `PublishManager` | Deploy via image registry | 🔲 future |

**Note**: `BakeManager` is an internal manager used by `ship` mode. There is no `fmd deploy bake` or `fmd bake` command exposed to users.

### Implementation status

| Mode/Manager | Status | Class |
|---|---|---|
| `pull` | ✅ CLI command | `PullManager` |
| `ship` | ✅ CLI command | `ShipManager` |
| `BakeManager` | ✅ internal only | `BakeManager` |
| `PublishManager` | 🔲 future | — |

---

## Manager Architecture

### Runner system

All managers use a `runner` + `host_runner` pair. `runner` handles container/remote commands. `host_runner` handles local host commands (hooks, scripts).

```
CommandRunner (ABC)
├── FMRunner        — compose.exec into running FM frappe service
├── HostRunner      — run_command_with_exit_code on local host
└── BuildRunner     — two sub-paths based on config.build_frappe:
      ├── build_frappe set   → DockerClient().run(builder_image, volume=bench)
      └── build_frappe None  → compose.exec(service="frappe")
```

`FMRunner` is used by `PullManager` for all container commands.
`BuildRunner` is used by `BakeManager`/`ShipManager` — it knows whether to spin up an ephemeral builder container or exec into a running compose service.

#### `BuildRunner` sub-path decision

`config.build_frappe` present?

```
YES → "offline image build"
      DockerClient().run(image=builder_image_name, volume=self.path:/workspace/frappe-bench)
      - Ephemeral container per command (rm=True)
      - No compose stack needed
      - Workdir: /workspace/frappe-bench (hardcoded)

NO  → "live FM deployment"
      compose_project.docker.compose.exec(service="frappe")
      - Execs into already-running compose frappe service
      - Requires FM stack to be up
      - Workdir: /workspace/{bench_dir.name}
```

### Mixin system

Shared bench operations live in `ops/` mixins. All mixins assume `self.runner`, `self.host_runner`, `self.printer`, `self.config`, `self.apps`, `self.bench_cli`, `self.fmx`, `self.bench_path`, `self.current`.

```
BenchMixin        — python_env_create, bench_setup_requiments, bench_build,
                    bench_restart, bench_symlink, configure_uv,
                    bench_install_all_apps_in_python_env,
                    _run_script, get_script_env
AppsMixin         — clone_apps, bench_install_apps
BackupMixin       — bench_db_and_configs_backup, bench_backup, bench_restore
SymlinksMixin     — configure_symlinks
CleanupMixin      — cleanup_releases, cleanup_backups
```

### Class hierarchy

```
PullManager(BackupMixin, AppsMixin, BenchMixin, SymlinksMixin, CleanupMixin)
  runner      = FMRunner
  host_runner = HostRunner

BakeManager(BenchMixin)
  runner      = BuildRunner
  host_runner = HostRunner
  bench_build — overrides BenchMixin (different flags: --hard-link, iterates bench_directory.apps)
  clone_apps  — overrides AppsMixin (parallel cloning, data_directory param)

ShipManager(BakeManager)
  runner        = BuildRunner       (local bake phase)
  host_runner   = HostRunner        (local host hooks)
  remote_runner = FMRunner          (remote finalization, DOCKER_HOST=ssh://user@server)
```

---

## `bench_build` divergence

`BenchMixin.bench_build` and `BakeManager.bench_build` are intentionally kept separate.

| | `BenchMixin` (pull mode) | `BakeManager` (bake/ship mode) |
|---|---|---|
| Build flag | `--production` | `--hard-link` |
| App iteration | `self.apps` config list (uses `app.app_name`) | `bench_directory.apps` dirs (resolves `app_config` by dir_name lookup) |
| Context | Live FM deployment | Offline image build / ship |

---

## Hook system

12 lifecycle hooks across 3 phases. Hooks run as shell scripts. Values can be inline script content or a path to a `.sh`/`.py` file.

### Phases

| Phase | Container hooks | Host hooks |
|---|---|---|
| `python_install` | `before_python_install`, `after_python_install` | `host_before_python_install`, `host_after_python_install` |
| `bench_build` | `before_bench_build`, `after_bench_build` | `host_before_bench_build`, `host_after_bench_build` |
| `restart` | `before_restart`, `after_restart` | `host_before_restart`, `host_after_restart` |

### Scope

- `restart` hooks — global config level only
- `python_install` hooks — per-app config (with global fallback)
- `bench_build` hooks — per-app config (with global fallback)

### Execution

- Container hooks → `_run_script(..., container=True)` → runs inside frappe container
- Host hooks → `_run_script(..., container=False)` → runs on host via `HostRunner`
- Per-app hooks get `APP_NAME` and `APP_PATH` in env
- All hooks get full config env via `get_script_env()`

---

## `ship` mode — detailed flow

```
Local runner
  ShipManager.ship()
    1. bake phase (inherited from BakeManager)
       ├── clone_apps(current)
       ├── chown_dir(...)
       ├── python_env_create(current)
       ├── bench_setup_requiments(current)
       ├── sync_configs_with_files(current)
       └── bench_build(current)

    2. rsync phase
       └── rsync -az --delete release_dir/ user@server:remote_path/release_dir/

    3. remote finalization (via DOCKER_HOST=ssh://user@server)
       ├── bench_symlink(remote_bench_dir)
       ├── remote_runner.restart_services(args, remote_bench_dir)   ← fmx restart
       └── bench_install_apps(remote_bench_dir)
```

### Config (`ship` section in `config.toml`)

```toml
[ship]
host = "user@server"           # SSH target
remote_path = "/path/on/server"  # deploy path on server
rsync_options = []             # extra rsync flags (optional)
```

### Files

| File | Purpose |
|---|---|
| `ship_manager.py` | `ShipManager(BakeManager)` |
| `config/ship.py` | `ShipConfig` pydantic model |
| `config/config.py` | Add `ship: Optional[ShipConfig]` |
| `commands/ship.py` | `fmd ship` CLI command |

---

## Refactor plan

### Phase 1 — Eliminate duplication

1. **`runner/build.py`** — new `BuildRunner(CommandRunner)` with `build_frappe` branching
2. **`runner/__init__.py`** — export `BuildRunner`
3. **`ops/bench.py`** — move real `_run_script` + `get_script_env` implementations into `BenchMixin` (merged from both managers)
4. **`bake_manager.py`** — extend `BenchMixin`, add `self.runner = BuildRunner(...)` + `self.host_runner = HostRunner(...)`, delete ~600 lines of duplicated ops
5. **`pull_manager.py`** — delete `_run_script` + `get_script_env` (now inherited from `BenchMixin`)
6. **`helpers.py`** — add `log_execution_time` + `extract_timestamp` (currently duplicated in both managers)

Deleted from `BakeManager` (replaced by `BenchMixin`):
`_run_script`, `get_script_env`, `configure_uv`, `python_env_create`, `bench_install_all_apps_in_python_env`, `bench_setup_requiments`, `bench_restart`, `bench_symlink`, `is_app_installed_in_site`

Kept in `BakeManager` (intentionally different):
`bench_build`, `clone_apps`, `chown_dir`, `setup_nvm_and_yarn`, `sync_configs_with_files`, `bake`, `is_baked`, `build_images`, `_build_frappe_base_image`, `_build_frappe_image`, `_build_nginx_image`

### Phase 2 — `ship` mode

1. **`config/ship.py`** — `ShipConfig(BaseModel)` with `host`, `remote_path`, `rsync_options`
2. **`config/config.py`** — add `ship: Optional[ShipConfig] = None`
3. **`ship_manager.py`** — `ShipManager(BakeManager)` with `rsync_release()` + `finalize_remote()`
4. **`commands/ship.py`** — `fmd ship` CLI command

### Phase 3 — `publish` mode *(future)*

1. After `bake`, SSH to server via `DOCKER_HOST`, swap compose service image, restart.
