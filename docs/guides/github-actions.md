# GitHub Action

Automate Frappe deployments from GitHub Actions using two strategies: **pull** (remote server pulls and builds) and **ship** (CI runner builds, rsyncs to remote).

## Strategies

| Strategy | Build location | Deploy target | When to use |
|----------|---------------|---------------|-------------|
| **pull** | Remote server | Same server | Server has enough CPU/RAM to build; simpler setup |
| **ship** | CI runner (Docker) | Remote server via rsync | Offload build from server; cross-arch builds |

---

## pull

The CI runner SSHes into the remote server and runs `fmd deploy pull` there. The server clones apps, builds the release, and switches — all on the server itself.

**Required secrets/vars**:

| Name | Type | Description |
|------|------|-------------|
| `GH_TOKEN` | secret | GitHub token for private repo access |
| `SSH_PRIVATE_KEY` | secret | Private key for the remote server |
| `SSH_SERVER` | secret | Remote server hostname or IP |
| `SSH_USER` | secret | SSH username (e.g. `frappe`) |
| `SITE_NAME` | var | Frappe site name (e.g. `mysite.example.com`) |
| `SSH_PORT` | var | SSH port — optional, defaults to `22` |

**Minimal workflow** (`.github/workflows/deploy-pull.yml`):

```yaml
name: Deploy (pull)

on:
  push:
    branches:
      - main
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy via pull
        uses: rtcamp/frappe-deployer@main
        with:
          command: pull
          sitename: ${{ vars.SITE_NAME }}
          config_path: .github/configs/site.toml
          gh_token: ${{ secrets.GH_TOKEN }}
          ssh_private_key: ${{ secrets.SSH_PRIVATE_KEY }}
          ssh_server: ${{ secrets.SSH_SERVER }}
          ssh_user: ${{ secrets.SSH_USER }}
```

**With all switch options**:

```yaml
      - name: Deploy via pull
        uses: rtcamp/frappe-deployer@main
        with:
          command: pull
          sitename: ${{ vars.SITE_NAME }}
          config_path: .github/configs/site.toml
          gh_token: ${{ secrets.GH_TOKEN }}
          ssh_private_key: ${{ secrets.SSH_PRIVATE_KEY }}
          ssh_server: ${{ secrets.SSH_SERVER }}
          ssh_user: ${{ secrets.SSH_USER }}
          ssh_port: ${{ vars.SSH_PORT || '22' }}
          migrate: "true"
          migrate_timeout: "300"
          drain_workers: "true"
          drain_workers_timeout: "300"
          skip_stale_workers: "true"
          maintenance_mode_phases: "migrate"
          worker_kill_timeout: "15"
```

---

## ship

The CI runner builds the release locally inside Docker (no Frappe Manager services needed), rsyncs it to the remote server, then SSHes in to run `fmd release switch`.

The config file must include a `[ship]` section pointing at the remote server:

```toml
[ship]
host = "192.168.1.100"
ssh_user = "frappe"
ssh_port = 22
```

**Required secrets/vars**: same as pull (`GH_TOKEN`, `SSH_PRIVATE_KEY`, `SSH_SERVER`, `SSH_USER`). No `SITE_NAME` — the site name comes from `site_name` in the TOML config.

**Minimal workflow** (`.github/workflows/deploy-ship.yml`):

```yaml
name: Deploy (ship)

on:
  push:
    branches:
      - main
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Deploy via ship
        uses: rtcamp/frappe-deployer@main
        with:
          command: ship
          config_path: .github/configs/site.toml
          gh_token: ${{ secrets.GH_TOKEN }}
          ssh_private_key: ${{ secrets.SSH_PRIVATE_KEY }}
          ssh_server: ${{ secrets.SSH_SERVER }}
          ssh_user: ${{ secrets.SSH_USER }}
```

**With all switch options**:

```yaml
      - name: Deploy via ship
        uses: rtcamp/frappe-deployer@main
        with:
          command: ship
          config_path: .github/configs/site.toml
          gh_token: ${{ secrets.GH_TOKEN }}
          ssh_private_key: ${{ secrets.SSH_PRIVATE_KEY }}
          ssh_server: ${{ secrets.SSH_SERVER }}
          ssh_user: ${{ secrets.SSH_USER }}
          ssh_port: ${{ vars.SSH_PORT || '22' }}
          migrate: "true"
          migrate_timeout: "300"
          drain_workers: "true"
          drain_workers_timeout: "300"
          skip_stale_workers: "true"
          maintenance_mode_phases: "migrate"
          worker_kill_timeout: "15"
          runner_image: "ghcr.io/my-org/fm-builder:latest"
```

**ship-only inputs**:

| Input | Default | Description |
|-------|---------|-------------|
| `runner_image` | auto-detected | Docker image used to build the release. Override when you need a pinned or custom builder. |
| `existing_release` | — | Skip the build step and deploy a release already present locally (format: `release_YYYYMMDD_HHMMSS`). |
| `skip_rsync` | `false` | Skip the rsync step — useful when the release is already on the remote server. |

---

## Shared inputs

Both `pull` and `ship` support the same switch-phase inputs:

| Input | Default | Description |
|-------|---------|-------------|
| `migrate` | `true` | Run `bench migrate` after switch |
| `migrate_timeout` | `300` | Seconds before migrate is killed |
| `migrate_command` | — | Override the migrate command entirely |
| `drain_workers` | `false` | Gracefully drain background workers before restart |
| `drain_workers_timeout` | `300` | Seconds to wait for workers to finish |
| `drain_workers_poll` | `5` | Poll interval while draining (seconds) |
| `skip_stale_workers` | `true` | Skip workers that haven't checked in recently |
| `skip_stale_timeout` | `15` | Seconds before a worker is considered stale |
| `worker_kill_timeout` | `15` | Seconds before force-killing workers |
| `worker_kill_poll` | `3.0` | Poll interval while waiting to kill workers |
| `maintenance_mode_phases` | `""` | Space-separated phases to enable maintenance mode: `drain`, `migrate` |
| `additional_commands` | — | Extra CLI flags appended to the `fmd deploy` invocation |
| `ssh_port` | `22` | SSH port for the remote server |
| `config_path` | — | Path to TOML config file, relative to repo root |
| `config_content` | — | Inline TOML config string (alternative to `config_path`) |
| `app_env` | — | Per-app env vars injected into build hooks — see [Per-app environment](#per-app-environment) |

---

## Per-app environment

Inject secrets into app hook scripts without storing them in the config file:

```yaml
      - name: Deploy
        uses: rtcamp/frappe-deployer@main
        with:
          command: pull   # or ship
          # ...
          app_env: |
            my-private-app:LICENSE_KEY=${{ secrets.MY_APP_LICENSE_KEY }}
            another-app:API_SECRET=${{ secrets.ANOTHER_API_SECRET }}
```

Format: one `app-name:KEY=VALUE` per line. The `app-name` prefix must match the Python module name of the app (last path segment of the repo, e.g. `godam_core` for `my-org/custom-app`). All declared vars are exported before any app's hook scripts run.

## Hooks

Each app can define up to 8 hooks in `[[apps]]`. The `[switch]` section has 4 more for restart-time.

**Build-phase hooks** (per-app, in `[[apps]]`):

| Hook | Runs in | When |
|------|---------|------|
| `before_bench_build` | container | Before `bench build` for this app |
| `after_bench_build` | container | After `bench build` for this app |
| `host_before_bench_build` | host | Before `bench build` for this app |
| `host_after_bench_build` | host | After `bench build` for this app |
| `before_python_install` | container | Before `uv pip install` for this app |
| `after_python_install` | container | After `uv pip install` for this app |
| `host_before_python_install` | host | Before `uv pip install` for this app |
| `host_after_python_install` | host | After `uv pip install` for this app |

**Switch-phase hooks** (global, in `[switch]`):

| Hook | Runs in | When |
|------|---------|------|
| `before_restart` | container | Before services restart |
| `after_restart` | container | After services restart |
| `host_before_restart` | host | Before services restart |
| `host_after_restart` | host | After services restart |

Hooks prefixed `host_` run on the host machine. All others run inside the Docker container. Each hook value is either an inline shell script or a path to a `.sh`/`.py` file.

Example config with hooks:

```toml
[[apps]]
repo = "my-org/custom-app"
ref = "main"
before_bench_build = """
npm ci
npm run build:prod
"""
host_after_bench_build = """
curl -s -X POST "$WEBHOOK_URL" -d "app=$APP_NAME built"
"""

[switch]
host_before_restart = "echo 'switching to new release'"
after_restart = "bench --site $SITE_NAME clear-cache"
```

Hook values are always inline shell. If the value is a path ending in `.sh` or `.py` (or starts with `/`, `./`, `~/`), fmd reads that file and runs its contents — but the file must exist **on the machine running the hook** at deploy time (remote server for `pull`; CI runner for `host_` hooks in `ship`). Repo-committed scripts don't automatically appear on the remote server, so inline scripts are the safest choice for cross-environment hooks.

Hook scripts receive these environment variables:

| Variable | Value |
|----------|-------|
| `BENCH_PATH` | Path to the `frappe-bench` symlink |
| `WORKSPACE_ROOT` | Path to the workspace root |
| `APPS` | Comma-separated list of installed app names |
| `SITE_NAME` | Frappe site name |
| `APP_NAME` | Current app name (build-phase hooks only) |
| `APP_PATH` | Path to the current app directory (build-phase hooks only) |

Plus every field from the config as an uppercase env var (e.g. `SITE_NAME`, `MIGRATE`, `PYTHON_VERSION`).

For multiline values (e.g. a `.env` file), base64-encode the secret and pass via `app_env`:

```yaml
          app_env: |
            my-app:DOTENV_B64=${{ secrets.MY_APP_DOTENV_B64 }}
```

Then decode inside the hook:

```bash
echo "${DOTENV_B64}" | base64 -d > /path/to/.env
```

---

## Config file setup

Both strategies load deployment configuration from a TOML file committed to the repo. Create `.github/configs/site.toml`:

**For pull**:

```toml
site_name = "mysite.example.com"

[[apps]]
repo = "frappe/frappe"
ref = "version-15"

[[apps]]
repo = "frappe/erpnext"
ref = "version-15"

[switch]
migrate = true
maintenance_mode = true
maintenance_mode_phases = ["migrate"]
backups = true
rollback = false
```

**For ship** (adds a `[ship]` section):

```toml
site_name = "mysite.example.com"

[[apps]]
repo = "frappe/frappe"
ref = "version-15"

[[apps]]
repo = "frappe/erpnext"
ref = "version-15"

[ship]
host = "192.168.1.100"
ssh_user = "frappe"
ssh_port = 22

[switch]
migrate = true
maintenance_mode = true
maintenance_mode_phases = ["migrate"]
backups = true
rollback = false
```

**With environment variable substitution:**

Config files support `${VAR_NAME}` or `$VAR_NAME` syntax for dynamic values from GitHub Actions environment:

```toml
site_name = "${SITE_NAME}"

[[apps]]
repo = "frappe/frappe"
ref = "${FRAPPE_VERSION}"

[[apps]]
repo = "${GITHUB_ORG}/custom-app"
ref = "main"

[ship]
host = "${SSH_SERVER}"
ssh_user = "${SSH_USER}"
ssh_port = 22

[switch]
migrate = true
backups = "${BACKUP_ENABLED}"
```

Then in your workflow:

```yaml
- name: Deploy
  uses: rtcamp/frappe-deployer@fmx/0
  env:
    SITE_NAME: mysite.example.com
    FRAPPE_VERSION: version-15
    GITHUB_ORG: my-org
    SSH_SERVER: 192.168.1.100
    SSH_USER: frappe
    BACKUP_ENABLED: "true"
  with:
    command: ship
    config_path: .github/configs/site.toml
    gh_token: ${{ secrets.GH_TOKEN }}
    ssh_private_key: ${{ secrets.SSH_PRIVATE_KEY }}
```

Undefined variables preserve original syntax (`${UNDEFINED}` stays as-is). See [Configuration Guide](./configuration.md#environment-variable-substitution) for details.

See [`example-config.toml`](../example-config.toml) for the full schema.

---

## Setting up secrets

In your GitHub repository: **Settings → Secrets and variables → Actions**

| Name | Where | Value |
|------|-------|-------|
| `GH_TOKEN` | Secrets | GitHub PAT with `repo` scope (for private repos) or `GITHUB_TOKEN` for public |
| `SSH_PRIVATE_KEY` | Secrets | Contents of the private key file (e.g. `cat ~/.ssh/id_ed25519`) |
| `SSH_SERVER` | Secrets | Remote server IP or hostname |
| `SSH_USER` | Secrets | SSH username on the remote server |
| `SITE_NAME` | Variables | Frappe site name — pull only |
| `SSH_PORT` | Variables | SSH port if not 22 — optional |

Generate a dedicated deploy key:

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/deploy_key -N ""
cat ~/.ssh/deploy_key        # → paste as SSH_PRIVATE_KEY secret
cat ~/.ssh/deploy_key.pub    # → append to ~/.ssh/authorized_keys on remote server
```
