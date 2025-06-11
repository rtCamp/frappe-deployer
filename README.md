# Frappe Deployer

A powerful CLI tool for managing and deploying Frappe applications with support for both host and Frappe Manager (FM) modes. Create timestamped releases, manage backups, and deploy with confidence.

## Key Features

- **Dual Deployment Modes**: Host and Frappe Manager (FM) support
- **Release Management**: Timestamped releases with rollback capability  
- **Backup & Restore**: Automated backups with compression and retention policies
- **Database Operations**: Cross-site migration and search/replace functionality
- **Custom Scripts**: Pre/post deployment hooks and app-specific build commands
- **Remote Workers**: Distributed deployment across multiple servers
- **Maintenance Mode**: Built-in maintenance pages with developer bypass tokens
- **Configuration Management**: TOML-based configuration with CLI overrides

## Quick Start

```bash
# Install frappe-deployer
pip install frappe-deployer

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

## Core Commands

### Configuration
```bash
# Configure a new site
frappe-deployer configure <site-name> --mode <fm|host>

# Configure with backup enabled
frappe-deployer configure my-site --mode fm --backups
```

### Deployment
```bash
# Deploy apps from repositories
frappe-deployer pull <site-name> \
  --apps frappe/frappe:version-14 \
  --apps frappe/erpnext:version-14 \
  --maintenance-mode

# Deploy with custom configuration
frappe-deployer pull my-site \
  --config-path config.toml \
  --verbose
```

### Maintenance Operations
```bash
# Enable maintenance mode
frappe-deployer enable-maintenance <site-name>

# Disable maintenance mode  
frappe-deployer disable-maintenance <site-name>

# Search and replace in database
frappe-deployer search-replace <site-name> "old-text" "new-text" --dry-run
```

### Cleanup Operations
```bash
# Cleanup old releases and backups
frappe-deployer cleanup <site-name> \
  --backup-retain-limit 5 \
  --release-retain-limit 3 \
  --show-sizes

# Auto-approve cleanup
frappe-deployer cleanup my-site --yes
```

### Remote Workers
```bash
# Enable remote worker
frappe-deployer remote-worker enable <site-name> \
  --server 192.168.1.100 \
  --ssh-user frappe

# Sync to remote worker
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
backups = true
rollback = true
releases_retain_limit = 3
verbose = false

# App configurations
[[apps]]
repo = "frappe/frappe"
ref = "version-14"

[[apps]]
repo = "frappe/erpnext"  
ref = "version-14"

# Custom scripts (FM mode)
fm_pre_script = '''
echo "Running pre-deployment checks..."
'''

fm_post_script = '''
echo "Running post-deployment tasks..."
bench migrate --site all
'''

# Host mode configuration
[host]
bench_path = "/home/frappe/frappe-bench"

# Remote worker configuration
[remote_worker]
server = "192.168.1.100"
ssh_user = "frappe"
ssh_port = 22
```

## Directory Structure

frappe-deployer organizes deployments with this structure:

```
./                                    # Your project root
├── deployment-data/                  # Persistent data directory
│   ├── sites/                        # Site files and databases
│   │   ├── common_site_config.json   # Shared configuration
│   │   └── <site-name>/               # Site-specific data
│   ├── config/                       # Configuration files  
│   └── logs/                         # Application logs
├── deployment-backup/                # Backup storage
│   └── release_YYYYMMDD_HHMMSS/      # Timestamped backups
└── release_YYYYMMDD_HHMMSS/          # Current release directory
    ├── apps/                         # Installed applications
    ├── sites -> ../deployment-data/sites  # Symlinked to data
    └── env/                          # Python virtual environment
```

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

## License

[License information]
