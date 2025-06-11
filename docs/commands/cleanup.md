# cleanup

Clean up old releases and backups with retention policies.

## Synopsis

```bash
frappe-deployer cleanup [SITE_NAME] [OPTIONS]
```

## Description

The `cleanup` command helps manage disk space by removing old:

- Backup directories beyond retention limit
- Release directories beyond retention limit  
- Cache directories and temporary files
- Previous bench directories

Interactive prompts allow selective cleanup, or use `--yes` for automation.

## Options

### Required
- `SITE_NAME` - Name of the site to clean up

### Retention Limits
- `--backup-retain-limit`, `-b` - Number of backup directories to keep (default: 0)
- `--release-retain-limit`, `-r` - Number of release directories to keep (default: 0)

### Automation
- `--yes`, `-y` - Auto-approve all cleanup operations without prompting
- `--show-sizes`, `-s` - Calculate and display directory sizes (default: true)

### Configuration
- `--config-path`, `-c` - Path to TOML configuration file
- `--verbose`, `-v` - Enable verbose output

## Examples

### Interactive Cleanup
```bash
frappe-deployer cleanup my-site
```

### Keep Recent Items
```bash
frappe-deployer cleanup my-site \
  --backup-retain-limit 5 \
  --release-retain-limit 3
```

### Automated Cleanup
```bash
frappe-deployer cleanup my-site \
  --backup-retain-limit 3 \
  --release-retain-limit 2 \
  --yes
```

### Skip Size Calculation
```bash
frappe-deployer cleanup my-site \
  --no-show-sizes \
  --yes
```

## What Gets Cleaned

### Always Protected
- Current active release (never deleted)
- Current site data in `deployment-data/`

### Conditionally Cleaned
- **Cache directories**: `.cache`, `deployment_tmp/`
- **Previous bench**: `prev_frappe_bench/` directory
- **Old backups**: Based on `--backup-retain-limit`
- **Old releases**: Based on `--release-retain-limit`

### Retention Logic
- **Backup retention**: Keeps N most recent backup directories by timestamp
- **Release retention**: Keeps N most recent releases, always preserving current
- **Zero retention**: When limit is 0, all items become eligible for cleanup

## Interactive Mode

When not using `--yes`, cleanup shows tables of items with:

- Index numbers for selection
- Directory names and sizes
- Full paths
- Selection prompts for each category

### Selection Syntax
- `1,3,5` - Select specific indices
- `all` - Select all items
- `<empty>` - Skip this category

## Directory Structure

Cleanup operates on this structure:
```
./
├── deployment-data/           # Protected - never cleaned
├── deployment-backup/         # Subject to backup retention
│   ├── release_20231201_120000/
│   └── release_20231202_130000/
├── release_20231201_120000/   # Subject to release retention
├── release_20231202_130000/   # Current - always protected
├── prev_frappe_bench/         # Cleaned if confirmed
└── .cache/                    # Cleaned if confirmed
```

## Safety Features

1. **Current Release Protection**: Active release never deleted
2. **Interactive Confirmation**: Each category requires approval
3. **Selective Cleanup**: Choose specific items to remove
4. **Size Reporting**: See disk space impact before deletion
5. **Verbose Logging**: Track what was cleaned

## Performance Notes

- **Size calculation**: Can be slow for large directories, use `--no-show-sizes` to skip
- **Network independence**: Cleanup works offline
- **Concurrent safe**: Safe to run while deployments are happening

## Configuration File

```toml
# Set default retention limits
backup_retain_limit = 5
release_retain_limit = 3
verbose = true
```

## Automation Example

```bash
#!/bin/bash
# Weekly cleanup script
frappe-deployer cleanup production-site \
  --backup-retain-limit 10 \
  --release-retain-limit 5 \
  --yes \
  --verbose
```

## See Also

- [pull](pull.md) - Creating new releases
- [Configuration Guide](../configuration.md) - Setting retention limits
