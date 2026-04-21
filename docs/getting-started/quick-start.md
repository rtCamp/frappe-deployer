# Quick Start

This guide walks you through your first deployment with fmd — from zero to a running Frappe site.

## Prerequisites

Make sure you have:

- [x] Python 3.10+ installed
- [x] Docker and Docker Compose V2 running
- [x] Frappe Manager installed (`fm --version` works)
- [x] fmd installed (`fmd --version` works)

If not, see [Requirements](requirements.md) and [Installation](installation.md).

## Step 1: Create a Frappe Manager Bench

First, create a bench using Frappe Manager. This sets up the Docker environment where your site will run.

```bash
fm create mysite --environment prod
```

This creates a production bench named `mysite`. The bench directory is created at:

```
~/frappe/sites/mysite/
```

!!! tip "Development vs Production"
    Use `--environment dev` for development benches with developer tools enabled.

## Step 2: Configure Your Deployment Workspace

Navigate to your bench directory and configure the fmd workspace:

```bash
cd ~/frappe/sites/mysite
fmd release configure mysite.localhost
```

This creates the workspace structure:

```
~/frappe/sites/mysite/workspace/
├── .cache/              # Build cache
└── deployment-data/     # Persistent data (sites, logs, config)
```

## Step 3: Deploy Frappe + ERPNext

!!! tip "Configuration Files for Repeated Deployments"
    Before running your first deployment, consider creating a `site.toml` file (see [Step 6](#step-6-using-a-configuration-file) below). This makes future deployments cleaner and easier to track in version control.

Now deploy your apps with a single command:

```bash
fmd deploy pull mysite.localhost \
  --app frappe/frappe:version-15 \
  --app frappe/erpnext:version-15 \
  --maintenance-mode \
  --backups
```

**What happens:**

1. Creates a new timestamped release (e.g., `release_20260416_143022`)
2. Clones app repositories from GitHub
3. Builds Frappe bench inside Docker container
4. Enables maintenance mode
5. Takes database backup
6. Runs migrations
7. Switches to the new release atomically (symlink update)
8. Restarts services
9. Disables maintenance mode

This typically takes 5-15 minutes depending on your internet speed and server resources.

## Step 4: Verify Deployment

Check that your site is running:

```bash
fmd info mysite.localhost
```

You should see output showing:

- Current release (e.g., `release_20260416_143022`)
- Installed apps (frappe, erpnext)
- Site status

List all releases:

```bash
fmd release list mysite.localhost
```

## Step 5: Access Your Site

!!! warning "Default Password Security"
    Change the default `admin` password immediately after first login. Go to **User Settings → Change Password** in the Frappe UI.

Your site is now live! Access it at:

```
http://mysite.localhost
```

Default credentials:

- **Username**: `Administrator`
- **Password**: `admin` (or the password you set during bench creation)

## Using a Configuration File

!!! tip "Best Practice: Use Configuration Files"
    Command-line flags are great for quick tests, but configuration files provide version control, reproducibility, and team collaboration benefits. Create a `site.toml` file and commit it to your repository.

For repeated deployments, use a config file instead of command-line flags.

Create `site.toml`:

```toml
site_name = "mysite.localhost"
bench_name = "mysite"
github_token = "ghp_your_token"  # Optional, for private repos

[[apps]]
repo = "frappe/frappe"
ref = "version-15"

[[apps]]
repo = "frappe/erpnext"
ref = "version-15"

[switch]
migrate = true
maintenance_mode = true
backups = true
```

Then deploy with:

```bash
fmd deploy pull --config site.toml
```

Much cleaner! See [Configuration Guide](../guides/configuration.md) for all available options.

## Common Workflows

### Update Apps (New Deployment)

To deploy updates (e.g., new app versions or code changes):

```bash
fmd deploy pull --config site.toml
```

This creates a new release with the latest code and switches to it.

### Rollback to Previous Release

If something goes wrong, instantly rollback:

```bash
fmd release list mysite.localhost
# Find the previous release timestamp
fmd release switch mysite.localhost release_20260415_120000
```

### Deploy with Custom Python Version

```bash
fmd deploy pull mysite.localhost \
  --app frappe/frappe:version-15 \
  --python-version 3.11
```

### Deploy a Monorepo App

For apps in subdirectories of a monorepo:

```bash
fmd deploy pull mysite.localhost \
  --app my-org/monorepo:main:apps/my-app
```

Format: `org/repo:ref:subdir_path`

## Next Steps

Now that you've deployed your first site, explore:

- **[Deploy Modes](../guides/deploy-modes.md)** — Learn about pull vs ship deployment strategies
- **[GitHub Actions](../guides/github-actions.md)** — Automate deployments from CI/CD
- **[Hooks](../guides/hooks.md)** — Customize build and deployment lifecycle
- **[Frappe Cloud Sync](../guides/frappe-cloud.md)** — Sync apps and databases from Frappe Cloud
- **[Configuration](../guides/configuration.md)** — Deep dive into all config options

## Troubleshooting

### Build fails during deployment

Check logs:

```bash
fm logs mysite
```

Common issues:

- **GitHub rate limit**: Set `GITHUB_TOKEN` environment variable
- **Network timeout**: Increase timeout or check internet connection
- **Disk space**: Ensure at least 5 GB free space

### Site not accessible

Verify the bench is running:

```bash
fm info mysite
```

If stopped, start it:

```bash
fm start mysite
```

### Migration errors

If migrations fail, fmd auto-rollbacks to the previous release (if `rollback = true` in config).

Check which release is active:

```bash
fmd info mysite.localhost
```

Manually switch if needed:

```bash
fmd release switch mysite.localhost release_YYYYMMDD_HHMMSS
```

For more troubleshooting, see [Troubleshooting Guide](../reference/troubleshooting.md).
