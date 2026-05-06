# Configuration

Complete guide for the fmd configuration file (`site.toml`).

## Quick Start

fmd uses TOML configuration files to define deployment settings. This eliminates long command-line flags and makes configurations reusable and version-controllable.

### Minimal Configuration

For a basic production deployment with Frappe + ERPNext:

```toml
site_name = "mysite.localhost"

[[apps]]
repo = "frappe/frappe"
ref = "version-15"

[[apps]]
repo = "frappe/erpnext"
ref = "version-15"

[switch]
maintenance_mode = true
backups = true
migrate = true
```

Deploy with:

```bash
fmd deploy pull --config site.toml
```

That's it! This configuration:

- ✅ Deploys Frappe v15 + ERPNext v15
- ✅ Enables maintenance mode during migration
- ✅ Takes automatic backups before switching
- ✅ Runs database migrations

### Configuration File Location

Store your config file anywhere:

- Project root: `site.toml`
- CI/CD: `.github/configs/site.toml`
- Per-environment: `config/staging.toml`, `config/prod.toml`

Reference it with `--config`:

```bash
fmd deploy pull --config .github/configs/site.toml
```

## Common Patterns

### Private Repositories

!!! tip "GitHub Token Best Practices"
    Never commit tokens directly to configuration files. Use environment variable substitution (`github_token = "${GITHUB_TOKEN}"`) and store tokens in CI/CD secrets or local environment variables. Generate tokens at [github.com/settings/tokens](https://github.com/settings/tokens) with `repo` scope.

```toml
github_token = "${GITHUB_TOKEN}"  # Environment variable substitution

[[apps]]
repo = "my-org/private-app"
ref = "main"
```

Set the token via environment:

```bash
export GITHUB_TOKEN=ghp_xxx
fmd deploy pull --config site.toml
```

### Monorepo Apps

For apps in subdirectories within a repository:

```toml
[[apps]]
repo = "my-org/monorepo"
ref = "main"
subdir_path = "apps/my-app"
```

See [Monorepo Apps Guide](monorepo-apps.md) for more details.

### Custom Build Hooks

Run custom scripts during deployment lifecycle:

```toml
[release.hooks]
before_install_all = "echo 'Starting installation...'"
after_build_apps = """
bench --site $SITE_NAME set-config developer_mode 0
bench --site $SITE_NAME clear-cache
"""

[switch.hooks]
before_restart = "supervisorctl stop all"
after_restart = "curl -f http://localhost:8000 || exit 1"
```

See [Hooks Guide](hooks.md) for all available hook points.

### Ship Mode (Build Locally, Deploy Remotely)

For offloading builds to CI runners or deploying to multiple servers:

```toml
site_name = "mysite.example.com"

[[apps]]
repo = "frappe/frappe"
ref = "version-15"

[ship]
host = "192.168.1.100"
ssh_user = "frappe"
ssh_port = 22

[switch]
migrate = true
backups = true
```

Deploy with:

```bash
fmd deploy ship --config site.toml
```

See [Deploy Modes Guide](deploy-modes.md) for pull vs ship comparison.

## Environment Variable Substitution

Configuration files support environment variable substitution using `${VAR_NAME}` or `$VAR_NAME` syntax. This allows dynamic configuration based on environment:

```toml
site_name = "${SITE_NAME}"
github_token = "${GITHUB_TOKEN}"

[[apps]]
repo = "frappe/frappe"
ref = "${FRAPPE_VERSION}"

[[apps]]
repo = "${GITHUB_ORG}/custom-app"
ref = "main"

[switch]
backups = "${BACKUPS_ENABLED}"
```

**Supported patterns:**
- `${VAR_NAME}` - Braced syntax (recommended)
- `$VAR_NAME` - Unbraced syntax
- Variable names must start with letter or underscore, contain only uppercase letters, numbers, and underscores

**Behavior:**
- Defined variables are replaced with their values
- Undefined variables preserve original syntax: `${UNDEFINED}` remains as-is
- Works in any string value (nested objects, lists, mixed strings)
- Non-string values (numbers, booleans) are not affected

**Usage with GitHub Actions:**

```yaml
- name: Deploy
  uses: rtcamp/frappe-deployer@fmx/0
  env:
    SITE_NAME: helpdesk.example.com
    FRAPPE_VERSION: version-15
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    BACKUPS_ENABLED: "true"
  with:
    config_file: .github/deploy.toml
```

---

??? info "Full Configuration Reference"
    Complete documentation of all available configuration options.

    ## Required Settings

    ### Site and Bench

    ```toml
    site_name = "mysite.localhost"
    ```

    The Frappe site name. This must match the site created in Frappe Manager.

    ```toml
    bench_name = ""
    ```

    The bench/container identifier. Defaults to `site_name` if not specified. Only set this if your bench directory name differs from your site name.

    ## Apps Configuration

    Define apps to install with `[[apps]]` sections. Each app is a separate block.

    ### Basic App

    ```toml
    [[apps]]
    repo = "frappe/frappe"
    ref = "version-15"
    ```

    - `repo`: Repository in format `"org/repo"` or full GitHub URL
    - `ref`: Git branch, tag, or commit hash

    ### Multiple Apps

    ```toml
    [[apps]]
    repo = "frappe/frappe"
    ref = "version-15"

    [[apps]]
    repo = "frappe/erpnext"
    ref = "version-15"

    [[apps]]
    repo = "frappe/hrms"
    ref = "main"
    ```

    Apps are installed in the order specified.

    ### Private Repositories

    ```toml
    github_token = "ghp_your_token_here"

    [[apps]]
    repo = "my-org/private-app"
    ref = "main"
    ```

    Set `github_token` at the top level to access private repositories.

    ### Monorepo Apps

    For apps in subdirectories:

    ```toml
    [[apps]]
    repo = "my-org/monorepo"
    ref = "main"
    subdir_path = "apps/my-app"
    ```

    See [Monorepo Apps Guide](monorepo-apps.md) for details.

    ### Symlinked Apps (Development)

    ```toml
    [[apps]]
    repo = "my-org/my-app"
    ref = "develop"
    symlink = true
    ```

    Symlink instead of copying — useful for development where you want to edit code directly.

        ### Clone Options

        ```toml
        [[apps]]
        repo = "frappe/erpnext"
        ref = "version-15"
        shallow_clone = true      # Default: true
        remote_name = "upstream"  # Default: "upstream"
        ```

        - `shallow_clone`: Use `--depth=1` for faster cloning (saves bandwidth and disk)
        - `remote_name`: Git remote name

        ## Release Configuration

        Control how releases are created and managed.

        ```toml
        [release]
        releases_retain_limit = 7
        python_version = "3.11"
        node_version = "20"
        ```

        ### Retention Limit

        ```toml
        releases_retain_limit = 7
        ```

        Number of releases to keep. Older releases are automatically deleted. Default: 7

        ### Python and Node Versions

        ```toml
        python_version = "3.11"
        node_version = "20"
        ```

        Pin specific versions for your release. If not specified, uses system defaults.

        ### Runner Mode

        ```toml
        mode = "exec"  # or "image"
        ```

        - `exec` (default): Run build in existing docker-compose containers
        - `image`: Run build in temporary containers (works without running services)

        ### Platform (Cross-Architecture)

        ```toml
        platform = "linux/arm64"
        ```

        Force a specific Docker platform. Useful for cross-architecture deployments (e.g., build on x86_64, deploy to ARM64).

        ## Switch Configuration

        Control behavior during release switch (activation).

        ```toml
        [switch]
        migrate = true
        migrate_timeout = 300
        maintenance_mode = true
        maintenance_mode_phases = ["migrate"]
        backups = true
        rollback = false
        search_replace = true
        ```

        ### Migration

        ```toml
        migrate = true
        migrate_timeout = 300
        ```

        - `migrate`: Run `bench migrate` during switch
        - `migrate_timeout`: Timeout in seconds for migrations (default: 300)

        ### Maintenance Mode

        ```toml
        maintenance_mode = true
        maintenance_mode_phases = ["migrate"]
        ```

        - `maintenance_mode`: Enable maintenance mode during switch
        - `maintenance_mode_phases`: When to enable (options: `"drain"`, `"migrate"`)

        See [Maintenance Mode Guide](maintenance-mode.md) for details.

        ### Backups

        ```toml
        backups = true
        backup_timeout = 600
        ```

        - `backups`: Take database backup before switch
        - `backup_timeout`: Timeout in seconds (default: 600)

        ### Rollback

        ```toml
        rollback = false
        ```

        Automatically rollback to previous release if switch fails. Default: false

        !!! warning "Auto-rollback Behavior"
            When `rollback = false` and a deployment fails, you'll need to manually investigate and fix the issue or rollback via `fmd release switch`. When `rollback = true`, fmd silently reverts to the previous release — which can hide problems. Only enable auto-rollback in automated environments where immediate investigation isn't possible.

        ### Search and Replace

        ```toml
        search_replace = true
        search_replace_pairs = []
        ```

        Run search-replace operations during switch. See [Search-Replace Command](../commands/search-replace.md).

        ### Worker Draining

        ```toml
        drain_workers = false
        drain_workers_timeout = 300
        skip_stale_workers = true
        skip_stale_timeout = 15
        worker_kill_timeout = 15
        ```

        Control background worker behavior during switch:

        - `drain_workers`: Wait for workers to finish jobs before switch
        - `drain_workers_timeout`: Max time to wait for workers (seconds)
        - `skip_stale_workers`: Skip workers that haven't processed jobs recently
        - `skip_stale_timeout`: Consider worker stale after N seconds of inactivity
        - `worker_kill_timeout`: Force-kill workers after this timeout

        ## Frappe Cloud Integration

        Sync apps, dependencies, or database from Frappe Cloud.

        ```toml
        [fc]
        api_key = "fc_your_key"
        api_secret = "fc_your_secret"
        site_name = "yoursite.frappe.cloud"
        team_name = "your-team"

        [release]
        use_fc_apps = true
        use_fc_deps = true

        [switch]
        use_fc_db = true
        ```

        - `use_fc_apps`: Import app list and commit hashes from FC
        - `use_fc_deps`: Import Python version from FC
        - `use_fc_db`: Download and restore latest FC database backup

        See [Frappe Cloud Sync Guide](frappe-cloud.md) for details.

        ## Ship Mode (Remote Deployment)

        Configure remote server for ship mode deployments.

        ```toml
        [ship]
        server_ip = "192.168.1.100"
        ssh_user = "frappe"
        ssh_port = 22
        remote_workspace_root = "/home/frappe/frappe/sites/mysite.localhost/workspace"
        ```

        See [Deploy Modes Guide](deploy-modes.md#ship-mode) for details.

        ## Remote Workers

        Enable remote workers to run background jobs on separate servers.

        ```toml
        [remote_worker]
        server_ip = "192.168.1.200"
        ssh_user = "frappe"
        ssh_port = 22
        ```

        See [Remote Workers Guide](remote-workers.md) for details.

        ## Hooks

        Customize build and deployment lifecycle with shell hooks.

        ### App-Level Hooks

        ```toml
        [[apps]]
        repo = "my-org/my-app"
        ref = "main"

        before_bench_build = """
        npm ci
        npm run build:prod
        """

        after_bench_build = """
        echo "Build complete for my-app"
        """
        ```

        ### Global Hooks

        ```toml
        [release]
        before_bench_build = """
        echo "Starting build..."
        """

        after_bench_build = """
        echo "Build complete!"
        """
        ```

        ### Host Hooks

        Prefix with `host_` to run on host instead of inside container:

        ```toml
        [[apps]]
        repo = "my-org/my-app"
        ref = "main"

        host_after_bench_build = """
        curl -X POST "$WEBHOOK_URL" -d "Build complete"
        """
        ```

        ### Available Hooks

        **Build phase (per-app and global):**

        - `before_bench_build`
        - `after_bench_build`
        - `before_python_install`
        - `after_python_install`

        **Switch phase (global only):**

        - `before_restart`
        - `after_restart`
        - `host_before_restart`
        - `host_after_restart`

        See [Hooks Guide](hooks.md) for detailed examples.

        ## Environment Variables in Hooks

        Hooks have access to these environment variables:

        - `$SITE_NAME`: Site name
        - `$APP_NAME`: Current app name (app-level hooks only)
        - `$RELEASE_DIR`: Release directory path
        - `$WORKSPACE_ROOT`: Workspace root path

        Custom env vars via `app_env`:

        ```toml
        [[apps]]
        repo = "my-org/my-app"
        ref = "main"
        app_env = { API_KEY = "secret123", ENV = "production" }
        ```

        ## Command-Line Overrides

        Most config file options can be overridden via CLI flags:

        ```bash
        fmd deploy pull --config site.toml \
          --maintenance-mode \
          --python-version 3.12 \
          --app frappe/frappe:develop
        ```

        CLI flags take precedence over config file values.

        ## Multiple Environments

        Use separate config files for different environments:

        ```
        .github/configs/
        ├── dev.toml
        ├── staging.toml
        └── prod.toml
        ```

        Then deploy with:

        ```bash
        fmd deploy pull --config .github/configs/prod.toml
        ```

        ## Validation

        fmd validates your config before deployment:

        - Required fields present
        - Valid TOML syntax
        - Reasonable timeout values
        - App format correctness

        Validation errors are shown immediately — fmd won't start building with invalid config.

        ## Next Steps

        - See [example-config.toml](https://github.com/rtcamp/fmd/blob/main/example-config.toml) for complete schema
        - Learn about [hooks](hooks.md) for customization
        - Set up [GitHub Actions](github-actions.md) for CI/CD
