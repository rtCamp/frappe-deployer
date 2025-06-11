# disable-maintenance

Disable maintenance mode for a site.

## Synopsis

```bash
frappe-deployer disable-maintenance SITE_NAME
```

## Description

Disables maintenance mode by removing the nginx configuration that shows the maintenance page, restoring normal site access.

Only works with FM mode deployments.

## Arguments

- `SITE_NAME` - Name of the site

## How It Works

1. **Remove Config**: Deletes the maintenance mode nginx configuration
2. **Service Restart**: Reloads nginx to apply changes  
3. **Restore Access**: Site becomes normally accessible to all users

## Examples

### Disable Maintenance
```bash
frappe-deployer disable-maintenance production-site
```

### Output Example
```
Maintenance mode disabled for site production-site
```

## Automatic Usage

Maintenance mode is automatically:
- **Enabled**: At the start of deployments (if configured)
- **Disabled**: At the end of successful deployments

## Use Cases

- **Post-deployment**: Restore access after maintenance work
- **Emergency recovery**: Quickly bring site back online
- **Manual control**: Override automatic maintenance mode

## Safety Features

- **Idempotent**: Safe to run multiple times
- **Error handling**: Graceful handling if config doesn't exist
- **Service restart**: Ensures changes take effect immediately

## File Operations

Removes maintenance configuration from:
```
/path/to/services/global-nginx-proxy/vhostd/SITE_NAME_location
```

## Limitations

- **FM mode only**: Host mode not supported
- **Site must exist**: Validates site existence before disabling
- **Nginx dependency**: Requires global nginx proxy service

## Troubleshooting

### Config Not Found
If maintenance was never enabled, the command succeeds with no action needed.

### Nginx Restart Fails
Check that:
- Docker services are running
- Nginx proxy container is healthy
- No syntax errors in nginx configuration

## See Also

- [enable-maintenance](enable-maintenance.md) - Enable maintenance mode
- [pull](pull.md) - Automatic maintenance mode handling
