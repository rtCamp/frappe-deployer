# enable-maintenance

Enable maintenance mode for a site.

## Synopsis

```bash
frappe-deployer enable-maintenance SITE_NAME
```

## Description

Enables maintenance mode by configuring nginx to display a maintenance page to users while allowing developer access via a bypass token.

Only works with FM mode deployments.

## Arguments

- `SITE_NAME` - Name of the site

## How It Works

1. **Nginx Configuration**: Creates location block for maintenance handling
2. **Bypass Token**: Generates secure random token for developer access
3. **Service Restart**: Reloads nginx to apply changes
4. **User Experience**: Shows maintenance page to regular visitors

## Developer Bypass

After enabling maintenance mode, developers can access the site using:

```
http://SITE_NAME/BYPASS_TOKEN/
```

The bypass token is displayed in the command output.

## Examples

### Enable Maintenance
```bash
frappe-deployer enable-maintenance production-site
```

### Output Example
```
Maintenance mode enabled for site production-site
Developer bypass URL: http://production-site/a1b2c3d4e5f6.../
```

## Maintenance Page

Users see a simple maintenance page:
```html
<!DOCTYPE html>
<html>
<head><title>Maintenance</title></head>
<body>
    <h1>Site Under Maintenance</h1>
    <p>We are performing scheduled maintenance. Please try again later.</p>
</body>
</html>
```

## Use Cases

- **Planned deployments**: Prevent user access during updates
- **Emergency maintenance**: Quick way to take site offline
- **Database operations**: Avoid conflicts during migrations
- **System updates**: Safely update underlying infrastructure

## Technical Details

### Nginx Configuration
Creates a location block that:
- Checks for bypass cookie
- Serves maintenance page to regular users  
- Allows developer access with valid token
- Proxies authenticated requests to application

### File Location
Maintenance config stored at:
```
/path/to/services/global-nginx-proxy/vhostd/SITE_NAME_location
```

## Limitations

- **FM mode only**: Host mode not supported
- **Site must exist**: Validates site existence before enabling
- **Nginx dependency**: Requires global nginx proxy service

## Security

- **Random tokens**: Cryptographically secure bypass tokens
- **Cookie-based**: Bypass uses HTTP-only cookies
- **Time-limited**: Tokens can be rotated by disabling/re-enabling

## See Also

- [disable-maintenance](disable-maintenance.md) - Disable maintenance mode
- [pull](pull.md) - Automatic maintenance mode during deployment
