# Command Reference

Complete reference for all frappe-deployer commands.

## Quick Navigation

- **[configure](configure.md)** - Initial deployment setup
- **[pull](pull.md)** - Main deployment command
- **[enable-maintenance / disable-maintenance](maintenance.md)** - Maintenance mode
- **[search-replace](search-replace.md)** - Database operations
- **[cleanup](cleanup.md)** - Workspace cleanup
- **[remote-worker](remote-worker.md)** - Remote worker management

## Global Options

All commands support these global options:

```bash
--verbose, -v          # Enable detailed output
--config-path PATH     # Path to TOML configuration file
--help                 # Show command help
```

## Command Categories

### Deployment Commands
- **[configure](configure.md)** - Set up deployment structure
- **[pull](pull.md)** - Deploy and update applications

### Maintenance Commands  
- **[maintenance](maintenance.md)** - Enable/disable maintenance mode
- **[cleanup](cleanup.md)** - Clean up old releases and backups

### Database Commands
- **[search-replace](search-replace.md)** - Search and replace in database

### Advanced Commands
- **[remote-worker](remote-worker.md)** - Manage distributed workers

## Common Patterns

### Basic Deployment
```bash
frappe-deployer pull my-site-name --config-path ./config.toml
```

### Deployment with CLI Overrides
```bash
frappe-deployer pull my-site-name \
  --config-path ./config.toml \
  --maintenance-mode \
  --verbose
```

### Emergency Operations
```bash
# Quick maintenance mode
frappe-deployer enable-maintenance my-site-name

# Emergency cleanup
frappe-deployer cleanup my-site-name --release-retain-limit 0 --yes
```

## Configuration Integration

Most commands can use configuration from:
- TOML files (`--config-path`)
- Direct content (`--config-content`)
- CLI arguments (highest priority)

See [Configuration Guide](../configuration.md) for details.

## Error Handling

Commands return standard exit codes:
- `0` - Success
- `1` - General error
- `2` - Configuration error
- `3` - Network/repository error

Use `--verbose` flag for detailed error information.
