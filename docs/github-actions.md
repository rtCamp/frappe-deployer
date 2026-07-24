# GitHub Actions

Deploy from CI with the composite action **`rtcamp/frappe-deployer@main`**. Pick a
strategy via `command`:

- `command: pull` — SSH into the remote server and run `fmd deploy pull` there (server
  builds and switches).
- `command: ship` — build the release in the runner (Docker), rsync it to the remote,
  then configure + switch remotely. Needs Docker Buildx and a `[ship]` config section.

See [Deploy modes](deploy-modes.md) for the trade-offs and [Configuration](configuration.md)
for the TOML.

## Secrets and variables

| Name | Kind | Description |
|------|------|-------------|
| `GH_TOKEN` | secret | GitHub token for private app repos |
| `SSH_PRIVATE_KEY` | secret | Private deploy key for the remote server |
| `SSH_SERVER` | secret | Remote hostname or IP (or use `[ship].host`) |
| `SSH_USER` | secret | SSH user, e.g. `frappe` (or use `[ship].ssh_user`) |
| `SITE_NAME` | variable | Frappe site name (pull; ship reads `site_name` from TOML) |

### Generate a deploy key

```bash
ssh-keygen -t ed25519 -C "fmd-deploy" -f fmd_deploy -N ""
```

Add the public key (`fmd_deploy.pub`) to the server's `~/.ssh/authorized_keys` for
`SSH_USER`, and store the private key (`fmd_deploy`) as the `SSH_PRIVATE_KEY` secret.

## Pull workflow

`.github/workflows/deploy-pull.yml`:

```yaml
name: Deploy (pull)

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: rtcamp/frappe-deployer@main
        with:
          command: pull
          sitename: ${{ vars.SITE_NAME }}
          config_path: .github/configs/site.toml
          gh_token: ${{ secrets.GH_TOKEN }}
          ssh_private_key: ${{ secrets.SSH_PRIVATE_KEY }}
          ssh_server: ${{ secrets.SSH_SERVER }}
          ssh_user: ${{ secrets.SSH_USER }}
```

## Ship workflow

Ship builds in the runner, so add Docker Buildx. The site name comes from the TOML, which
must include a `[ship]` section pointing at the remote:

```toml
site_name = "mysite.example.com"

[ship]
host = "192.168.1.100"
ssh_user = "frappe"
ssh_port = 22
```

`.github/workflows/deploy-ship.yml`:

```yaml
name: Deploy (ship)

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: docker/setup-buildx-action@v3

      - uses: rtcamp/frappe-deployer@main
        with:
          command: ship
          config_path: .github/configs/site.toml
          gh_token: ${{ secrets.GH_TOKEN }}
          ssh_private_key: ${{ secrets.SSH_PRIVATE_KEY }}
          ssh_server: ${{ secrets.SSH_SERVER }}
          ssh_user: ${{ secrets.SSH_USER }}
```

## Inputs

Common inputs: `command`, `config_path` (or inline `config_content`, plus
`config_overrides` for per-environment merges), `sitename` (pull), `gh_token`,
`ssh_private_key`, `ssh_server`, `ssh_user`, `ssh_port`. Switch overrides: `migrate`,
`migrate_timeout`, `maintenance_mode`, `maintenance_mode_phases`, `backups`, `rollback`.
Ship-only: `existing_release`, `skip_rsync`.

For the full, authoritative input reference and defaults, see **`action.yml`** at the repo
root.
