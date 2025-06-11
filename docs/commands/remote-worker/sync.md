# remote-worker sync

Sync workspace to remote worker server.

## Synopsis

```bash
frappe-deployer remote-worker sync SITE_NAME [OPTIONS]
```

## Description

The `sync` command synchronizes the workspace from the main server to the remote worker by:

1. Stopping remote worker services to prevent conflicts
2. Using rsync to efficiently transfer files
3. Linking worker-specific configuration files
4. Starting only worker services (not web services)

## Arguments

- `SITE_NAME` - Name of the site to sync

## Options

### Remote Server Configuration
- `--server`, `-s` - Remote server IP address or domain name
- `--ssh-user`, `-u` - SSH username (default: frappe)
- `--ssh-port`, `-p` - SSH port number (default: 22)

### Additional Sync Options
- `--include-dir`, `-d` - Additional directories to sync (can be repeated)
- `--include-file`, `-f` - Additional files to sync (can be repeated)

### Configuration
- `--config-path` - Path to TOML configuration file
- `--verbose`, `-v` - Enable verbose output

## Examples

### Basic Sync
```bash
frappe-deployer remote-worker sync my-site \
  --server 192.168.1.100
```

### Sync with Additional Files
```bash
frappe-deployer remote-worker sync my-site \
  --server 192.168.1.100 \
  --include-dir custom_apps \
  --include-file special_config.json
```

### With Configuration File
```bash
frappe-deployer remote-worker sync my-site \
  --config-path worker-config.toml
```

## What Gets Synced

### Base Directories
- **Release directory**: Current timestamped release
- **Deployment data**: Sites, config, and logs (excluding large files)

### Excluded Items
- **Large files**: `sites/*/public/files/**`, `sites/*/private/**`
- **Temporary files**: `.git/**`, `node_modules/**`, `__pycache__/**`
- **Cache files**: `.cache/**`, `*.pyc`, `*.log`

### Additional Includes
Items specified in configuration or CLI:
```toml
[remote_worker]
include_dirs = ["custom_apps", "backup_scripts"]
include_files = ["production.env", "worker_config.json"]
```

## Sync Process

### 1. Service Management
```bash
# Stop all services except schedule
docker-compose -f docker-compose.yml down
docker-compose -f docker-compose.yml up -d schedule

# Start worker services
docker-compose -f docker-compose.workers.yml up -d
```

### 2. File Transfer
Uses rsync with optimized settings:
- **Archive mode**: Preserves permissions and timestamps
- **Compression**: Reduces transfer time
- **Checksums**: Ensures data integrity
- **Delete**: Removes obsolete files

### 3. Configuration Linking
- **Symlinks worker configs**: Links worker-specific JSON files
- **Handles bench symlink**: Updates frappe-bench symlink target
- **Creates required directories**: Ensures all needed paths exist

## Performance Optimization

### Rsync Options Used
```bash
rsync -avz --delete --checksum \
  --exclude=**/.git/** \
  --exclude=**/node_modules/** \
  --exclude=**/__pycache__/** \
  --exclude=sites/*/public/files/** \
  --exclude=sites/*/private/** \
  SOURCE/ user@server:DEST/
```

### Network Efficiency
- **Compression**: Reduces bandwidth usage
- **Incremental**: Only transfers changed files
- **Parallel**: Multiple rsync operations for different directories

## Directory Structure on Worker

After sync, remote worker has:
```
/path/to/frappe-benches/SITE_NAME/workspace/
├── deployment-data/              # Synced (excluding large files)
├── release_YYYYMMDD_HHMMSS/      # Current release
├── frappe-bench -> release_*/    # Symlink to current release
└── custom_apps/                  # Additional included directories
```

## Configuration File Example

```toml
[remote_worker]
server = "192.168.1.100"
ssh_user = "frappe"
ssh_port = 22
workspace_path = "/home/frappe/workspace"
include_dirs = ["custom_apps", "private_scripts"]
include_files = ["worker.env", "logging.conf"]
```

## Service Management

### Worker Services Started
- **Background workers**: Process queued jobs
- **Scheduler**: Handle scheduled tasks
- **Queue processors**: Manage job queues

### Services NOT Started
- **Web server**: nginx/gunicorn for HTTP requests
- **Database**: MariaDB (connects to main server)
- **Redis cache**: Redis for caching (connects to main server)

## Troubleshooting

### Sync Failures
Check network connectivity:
```bash
# Test SSH connection
ssh frappe@192.168.1.100 "echo 'SSH OK'"

# Test rsync manually
rsync -avz --dry-run ./test-file frappe@192.168.1.100:/tmp/
```

### Large File Issues
Exclude problematic directories:
```bash
# Add to rsync excludes in configuration
exclude_patterns = [
  "--exclude=large_directory/**",
  "--exclude=*.iso"
]
```

### Permission Errors
Ensure SSH user has proper permissions:
```bash
# On remote server
sudo chown -R frappe:frappe /path/to/workspace
chmod -R 755 /path/to/workspace
```

## Monitoring

### Check Sync Progress
Use `--verbose` flag to see detailed progress:
```bash
frappe-deployer remote-worker sync my-site \
  --server 192.168.1.100 \
  --verbose
```

### Verify Worker Services
On remote server:
```bash
docker ps
docker-compose -f docker-compose.workers.yml logs
```

## Best Practices

1. **Regular syncing**: Sync after each deployment
2. **Monitor disk space**: Ensure adequate space on worker
3. **Network stability**: Use stable network connections
4. **Backup verification**: Ensure backups include worker data
5. **Service monitoring**: Monitor worker service health

## See Also

- [remote-worker enable](enable.md) - Initial worker setup
- [pull command](../pull.md) - Main deployment with worker sync
- [Configuration Guide](../../configuration.md) - Remote worker configuration
