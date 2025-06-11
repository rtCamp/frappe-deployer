# pull

Deploy apps and create new releases.

## Synopsis

```bash
frappe-deployer pull [SITE_NAME] [OPTIONS]
```

## Description

The `pull` command is the core deployment command that:

1. Creates a new timestamped release directory
2. Clones specified app repositories
3. Sets up Python virtual environment
4. Installs dependencies and builds apps
5. Runs database migrations
6. Switches to the new release atomically

## Options

### Required
- `SITE_NAME` - Name of the site to deploy

### Apps
- `--apps`, `-a` - App in format `org/repo:branch` (can be repeated)

### Configuration
- `--config-path` - Path to TOML configuration file
- `--config-content` - TOML configuration as string
- `--mode`, `-m` - Deployment mode: `fm` or `host`

### Deployment Settings
- `--maintenance-mode` - Enable maintenance mode during deployment
- `--backups` - Enable/disable backup creation
- `--rollback` - Enable/disable rollback on failure
- `--search-replace` - Enable search/replace in database
- `--run-bench-migrate` - Enable/disable `bench migrate`

### Python Environment
- `--python-version`, `-p` - Python version for virtual environment
- `--uv` - Use UV package manager instead of pip

### GitHub Integration
- `--github-token` - GitHub personal access token
- `--remove-remote` - Remove git remote after cloning

### Host Mode Options
- `--host-bench-path` - Path to existing bench directory

### FM Mode Options  
- `--fm-restore-db-from-site` - Import database from another site
- `--restore-db-file-path` - Restore from database backup file

### Release Management
- `--releases-retain-limit` - Number of releases to keep

### Output
- `--verbose`, `-v` - Enable detailed output

## Examples

### Basic Deployment
```bash
frappe-deployer pull my-site \
  --apps frappe/frappe:version-14 \
  --apps frappe/erpnext:version-14
```

### With Configuration File
```bash
frappe-deployer pull my-site --config-path production.toml
```

### Maintenance Mode Deployment
```bash
frappe-deployer pull my-site \
  --apps frappe/frappe:version-14 \
  --maintenance-mode \
  --verbose
```

### Host Mode Deployment
```bash
frappe-deployer pull my-site \
  --mode host \
  --host-bench-path /home/frappe/frappe-bench \
  --apps frappe/frappe:version-14
```

### Database Migration
```bash
frappe-deployer pull new-site \
  --apps frappe/frappe:version-14 \
  --fm-restore-db-from-site source-site \
  --search-replace
```

### Using UV Package Manager
```bash
frappe-deployer pull my-site \
  --config-path config.toml \
  --uv \
  --python-version 3.10
```

## Configuration File Example

```toml
site_name = "my-site"
mode = "fm"
maintenance_mode = true
backups = true
verbose = true

[[apps]]
repo = "frappe/frappe"
ref = "version-14"

[[apps]]
repo = "frappe/erpnext"
ref = "version-14"

fm_post_script = '''
echo "Running post-deployment tasks..."
bench migrate --site all
'''
```

## Workflow

1. **Backup**: Current state backed up (if enabled)
2. **Clone**: App repositories cloned to new release
3. **Setup**: Python environment and dependencies installed
4. **Build**: Apps built with custom pre/post scripts
5. **Maintenance**: Site put in maintenance mode (if enabled)
6. **Switch**: Symlink updated to new release
7. **Migrate**: Database migrations run
8. **Install**: New apps installed in site
9. **Cleanup**: Old releases cleaned up
10. **Complete**: Maintenance mode disabled

## Error Handling

- **Rollback**: If rollback is enabled, previous release is restored on failure
- **Cleanup**: Temporary files and failed releases are cleaned up
- **Logging**: Detailed logs available with `--verbose`

## See Also

- [configure](configure.md) - Initial site setup
- [cleanup](cleanup.md) - Release management
- [Configuration Guide](../configuration.md) - TOML configuration
