# Quick Start Guide

Get your first Frappe deployment running in 5 minutes.

## Prerequisites

- [frappe-deployer installed](installation.md)
- Basic familiarity with Frappe/ERPNext
- Choose your deployment mode: [FM vs Host](deployment-modes.md)

## Step 1: Configure Your Site

Choose your deployment mode and configure:

### Option A: Frappe Manager (FM) Mode
```bash
frappe-deployer configure my-site-name --mode fm --backups
```

### Option B: Host Mode
```bash
frappe-deployer configure my-site-name --mode host --host-bench-path /path/to/bench --backups
```

## Step 2: Deploy Your Apps

Deploy Frappe with ERPNext:

```bash
frappe-deployer pull my-site-name \
  -a frappe/frappe:version-14 \
  -a frappe/erpnext:version-14 \
  --maintenance-mode \
  --verbose
```

## Step 3: Verify Deployment

Check that your site is running:

```bash
# For FM mode
fm list

# For host mode
bench --site my-site-name version
```

## What Just Happened?

1. **Configuration**: Created deployment structure in `./deployment-data/`
2. **Release Creation**: Built timestamped release directory
3. **App Installation**: Cloned and installed specified apps
4. **Database Migration**: Updated database schema
5. **Maintenance Mode**: Enabled during deployment, disabled after

## Directory Structure

After deployment, you'll see:

```
./
├── deployment-data/           # Persistent data
│   ├── sites/
│   ├── config/
│   └── logs/
├── deployment-backup/         # Backup storage
└── release_20231201_143022/   # Current release (symlinked)
```

## Next Steps

- **Configure apps**: [Configuration Guide](configuration.md)
- **Set up backups**: [Backup & Restore](backup-restore.md)
- **Learn commands**: [Command Reference](commands/)
- **Production setup**: [Production Deployment Example](examples/production-deployment.md)

## Common Issues

- **Permission errors**: Ensure proper directory permissions
- **GitHub access**: Set up [GitHub token](configuration.md#github-token) for private repos
- **Python version**: Verify Python 3.8+ compatibility

See [Troubleshooting Guide](troubleshooting.md) for more help.
