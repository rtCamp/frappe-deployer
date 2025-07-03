# Frappe Deployer

A powerful CLI tool for managing and deploying Frappe applications with support for both host and Frappe Manager (FM) modes. Create timestamped releases, manage backups, and deploy with confidence.

## Key Features

- **Dual Deployment Modes:** Host and Frappe Manager (FM) support
- **Release Management:** Timestamped releases with rollback capability  
- **Backup & Restore:** Automated backups with compression and retention policies
- **Database Operations:** Cross-site migration, restore, and search/replace functionality
- **Symlink & Subdirectory App Support:** Symlink apps (including subdirectory apps) for efficient workspace management; configurable globally or per-app
- **Custom Scripts:** Pre/post deployment hooks and per-app build commands (`fm_pre_build`, `fm_post_build`)
- **Remote Workers:** Distributed deployment across multiple servers
- **Maintenance Mode:** Built-in maintenance pages with developer bypass tokens
- **Configuration Management:** TOML-based configuration with CLI overrides
- **Frappe Cloud Integration:** Import backups and config directly from Frappe Cloud
- **Python Version Management:** Specify Python versions; UV support for fast Python environments

## Quick Start

```bash
# Install latest frappe-deployer
pip install git+ssh://git@github.com/rtcamp/frappe-deployer.git@main

# Configure a new site (FM mode)
frappe-deployer configure my-site-name --mode fm

# Deploy Frappe and ERPNext
frappe-deployer pull my-site-name \
  -a frappe/frappe:version-14 \
  -a frappe/erpnext:version-14 \
  --maintenance-mode \
  --verbose

# Check deployment status
frappe-deployer --version
```

## Installation

```bash
# Install from PyPI (when available)
pip install frappe-deployer

# Install from source
git clone <repository-url>
cd frappe-deployer  
pip install -e .
```

### CLI Command Reference

```bash
# Configure a new site
frappe-deployer configure <site-name> --mode <fm|host> [--backups] [--config-path <path>]

# Deploy apps from repositories
frappe-deployer pull <site-name> \
  --apps frappe/frappe:version-14 \
  --apps frappe/erpnext:version-14 \
  --maintenance-mode

# Clone apps (with symlink/subdir support)
frappe-deployer clone <site-name> \
  --apps custom-org/custom-app:main:apps/custom-app --symlink-subdir-apps

# Show release info
frappe-deployer info <site-name>

# Search and replace in database
frappe-deployer search-replace <site-name> "old-text" "new-text" --dry-run

# Cleanup old releases and backups
frappe-deployer cleanup <site-name> \
  --backup-retain-limit 5 \
  --release-retain-limit 3 \
  --show-sizes \
  --yes

# Remote worker management
frappe-deployer remote-worker enable <site-name> \
  --server 192.168.1.100 \
  --ssh-user frappe

frappe-deployer remote-worker sync <site-name> \
  --server 192.168.1.100
```

## Configuration

Create a `config.toml` file:

```toml
site_name = "my-site"
mode = "fm"  # or "host"
python_version = "3.10"
github_token = "ghp_xxxxxxxxxxxx"  # Optional for private repos

# Deployment settings
maintenance_mode = true
maintenance_mode_phases = ["migrate", "start"]
backups = true
rollback = true
releases_retain_limit = 3
verbose = false
uv = true
symlink_subdir_apps = true  # Symlink all subdirectory apps by default

# App configurations
[[apps]]
repo = "frappe/frappe"
ref = "version-14"
symlink = false (default)

[[apps]]
repo = "frappe/erpnext"  
ref = "version-14"
symlink = false (default)

[[apps]]
repo = "custom-org/custom-app"
ref = "main"
subdir_path = "apps/custom-app"
symlink = true  # Symlink only this app

# Custom scripts (FM mode)
fm_pre_script = '''
echo "Running pre-deployment checks..."
'''

fm_post_script = '''
echo "Running post-deployment tasks..."
bench migrate --site all
'''

fm_pre_build = '''
echo "Pre-build for all apps"
'''

fm_post_build = '''
echo "Post-build for all apps"
'''

# Host mode configuration
[host]
bench_path = "/home/frappe/frappe-bench"

# Frappe Cloud integration
[fc]
team_name = "my-team"
api_key = "fc_xxxxxxxxxxxx"
api_secret = "fc_yyyyyyyyyyyy"
site_name = "my-site"
use_apps = true
use_deps = true

# Remote worker configuration
[remote_worker]
server = "192.168.1.100"
ssh_user = "frappe"
ssh_port = 22
```

## Directory Structure

```
./                                    # Your project root
├── deployment-data/                  # Persistent data directory
│   ├── sites/                        # Site files and databases
│   │   ├── common_site_config.json   # Shared configuration
│   │   └── <site-name>/              # Site-specific data
│   ├── apps/                         # Symlinked app directories, organized by release
│   │   └── release_YYYYMMDD_HHMMSS/  # Release-specific symlinked apps
│   │       └── <app>_clone /         # Symlinked app directory for this release
│   ├── config/                       # Configuration files  
│   └── logs/                         # Application logs
├── deployment-backup/                # Backup storage
│   └── release_YYYYMMDD_HHMMSS/      # Timestamped backups
├── .cache/                           # Python venv and workspace cache
├── prev_frappe_bench/                # Previous bench directory (for rollback)
└── release_YYYYMMDD_HHMMSS/          # Current release directory
    ├── apps/                         # Installed applications
    ├── sites -> ../deployment-data/sites  # Symlinked to data
    └── env/                          # Python virtual environment
```

> **Note:**  
> The `deployment-data/apps/` directory contains symlinked app directories, organized by release.  
> For each release, symlinked apps are placed under `deployment-data/apps/<release>/<app>/`.  
> This allows each release to maintain its own set of symlinked apps, supporting efficient workspace management and rollback.

## Deployment Modes

### Frappe Manager (FM) Mode
- **Container-based**: Uses Docker containers for isolation
- **Built-in services**: Database, Redis, and other services managed automatically  
- **Simplified setup**: Minimal host configuration required
- **Best for**: Development, staging, and containerized production

### Host Mode  
- **Direct installation**: Apps installed directly on the host system
- **Manual services**: You manage database, Redis, and other services
- **More control**: Direct access to all system components
- **Best for**: Traditional production deployments

---

#### Symlink & Subdirectory App Support

- Apps can be symlinked instead of copied for efficient workspace management.
- For apps in subdirectories (e.g., monorepos), use `subdir_path` in the app config.
- Symlinking can be enabled globally (`symlink_subdir_apps = true`) or per-app (`symlink = true`).
- Example:
  ```toml
  [[apps]]
  repo = "custom-org/custom-app"
  ref = "main"
  subdir_path = "apps/custom-app"
  symlink = true
  ```

---

#### Frappe Cloud Integration

- You can import backups and config directly from Frappe Cloud by specifying `[fc]` in your config.
- Set `use_apps = true` and/or `use_deps = true` to automatically import app and dependency info.
- The deployer will fetch the latest backup and config, and merge with your local settings.

---

#### Troubleshooting

- **App repo inaccessible:** Ensure all app repos are public or provide a valid `github_token`.
- **Symlink errors:** If using symlinks, ensure the target directories exist and are accessible.
- **Frappe Cloud integration:** Make sure your API credentials are correct and the site exists.
- **Backup/restore issues:** Only apps with a valid `apps/frappe` directory will trigger DB backup.

---

#### Contributing & Testing

- See `frappe_deployer/commands/test.py` for test commands.
- To run tests:  
  ```bash
  python -m frappe_deployer.commands.test
  ```

---

## Documentation

- **[Quick Start Guide](docs/quick-start.md)** - Get started in 5 minutes
- **[Installation Guide](docs/installation.md)** - Setup and requirements  
- **[Configuration Reference](docs/configuration.md)** - Complete TOML configuration
- **[Core Concepts](docs/concepts.md)** - Understanding the architecture
- **[Command Reference](docs/commands/)** - All available commands
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues and solutions

## Requirements

- Python 3.8 or higher
- Git
- Docker and Docker Compose (for FM mode)
- Frappe Manager (for FM mode)
- System access for bench management (for Host mode)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## GitHub Action Usage

You can use frappe-deployer as a reusable GitHub Action in your repositories.

### Setup

1. **Add your deployment configuration** to your repository:
   ```
   your-repo/
   ├── .github/
   │   ├── workflows/
   │   │   └── deploy.yml
   │   └── deploy_configs/
   │       ├── staging.toml
   │       └── production.toml
   ```

2. **Create a workflow file** (e.g., `.github/workflows/deploy.yml`):
   ```yaml
   name: Deploy Application
   
   on:
     push:
       branches: [main]
     workflow_dispatch:
       inputs:
         environment:
           description: 'Environment to deploy'
           required: true
           default: 'staging'
           type: choice
           options:
             - staging
             - production
         use_maintenance_mode:
           description: 'Enable maintenance mode'
           type: boolean
           default: true
         use_bench_migrate:
           description: 'Run bench migrate'
           type: boolean
           default: true
   
   jobs:
     deploy:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         
         - name: Deploy with frappe-deployer
           uses: rtcamp/frappe-deployer@v1  # Use specific version tag
           with:
             environment: ${{ inputs.environment || 'staging' }}
             ssh_private_key: ${{ secrets.SSH_PRIVATE_KEY }}
             ssh_server: ${{ secrets.SSH_SERVER }}
             ssh_user: ${{ secrets.SSH_USER }}
             github_token: ${{ secrets.GITHUB_TOKEN }}
             use_maintenance_mode: ${{ inputs.use_maintenance_mode || 'true' }}
             use_bench_migrate: ${{ inputs.use_bench_migrate || 'true' }}
             verbose: 'true'
   ```

### Action Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `environment` | Environment name (matches TOML config filename) | Yes | - |
| `ssh_private_key` | SSH private key for deployment | Yes | - |
| `ssh_server` | SSH server hostname/IP | Yes | - |
| `ssh_user` | SSH username | No | `frappe` |
| `github_token` | GitHub token for private repos | Yes | - |
| `config_path` | Path to config directory | No | `.github/deploy_configs` |
| `use_maintenance_mode` | Enable maintenance mode | No | `true` |
| `use_bench_migrate` | Run bench migrate | No | `true` |
| `additional_commands` | Additional CLI flags | No | - |
| `allowed_users` | Comma-separated allowed users | No | - |
| `verbose` | Enable verbose logging | No | `false` |

### Required Secrets

Configure these secrets in your repository settings:

- `SSH_PRIVATE_KEY` - SSH private key for server access
- `SSH_SERVER` - Target server hostname/IP  
- `SSH_USER` - SSH username (or use `ssh_user` input)
- `GITHUB_TOKEN` - For accessing private repositories

### Example Configurations

**staging.toml**:
```toml
site_name = "myapp-staging"
mode = "fm"
python_version = "3.11"
maintenance_mode = true
backups = true
verbose = true

[[apps]]
repo = "frappe/frappe"
ref = "version-15"

[[apps]]
repo = "myorg/myapp"
ref = "develop"
```

**production.toml**:
```toml
site_name = "myapp-production"  
mode = "fm"
python_version = "3.11"
maintenance_mode = true
backups = true
releases_retain_limit = 5

[[apps]]
repo = "frappe/frappe"
ref = "version-15"

[[apps]]
repo = "myorg/myapp"
ref = "main"
```

### Migration from Manual Setup

If you're currently copying deployment scripts to each repository, you can migrate by:

1. **Remove copied files** from individual repos:
   - `.github/deploy/addon.sh`
   - `.github/deploy/helpers.sh`
   - `.github/workflows/deploy-common.yml`

2. **Replace with action usage**:
   ```yaml
   # Old way - using copied files
   jobs:
     deploy:
       uses: ./.github/workflows/deploy-common.yml
   
   # New way - using action
   jobs:
     deploy:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: rtcamp/frappe-deployer@v1
           with:
             environment: 'production'
             # ... other inputs
   ```

3. **Keep your TOML configs** - they work the same way

## License

[License information]
