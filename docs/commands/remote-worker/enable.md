# remote-worker enable

Enable remote worker configuration for a site.

## Synopsis

```bash
frappe-deployer remote-worker enable SITE_NAME [OPTIONS]
```

## Description

The `enable` command configures a site for remote worker deployment by:

1. Finding available ports for Redis queue exposure
2. Configuring Docker Compose to expose database and Redis services
3. Creating worker-specific configuration files
4. Setting up network connectivity between servers

## Arguments

- `SITE_NAME` - Name of the site to configure for remote workers

## Options

### Remote Server Configuration
- `--server`, `-s` - Remote server IP address or domain name
- `--ssh-user`, `-u` - SSH username (default: frappe)
- `--ssh-port`, `-p` - SSH port number (default: 22)

### Configuration
- `--config-path` - Path to TOML configuration file
- `--verbose`, `-v` - Enable verbose output
- `--force` - Force recreate config files if they exist

## Examples

### Basic Remote Worker Setup
```bash
frappe-deployer remote-worker enable my-site \
  --server 192.168.1.100 \
  --ssh-user frappe
```

### With Configuration File
```bash
frappe-deployer remote-worker enable my-site \
  --config-path worker-config.toml
```

### Force Recreate Configs
```bash
frappe-deployer remote-worker enable my-site \
  --server 192.168.1.100 \
  --force
```

## What It Does

### Port Configuration
- **Finds available port**: Scans for unused ports starting from 11000
- **Redis queue exposure**: Exposes Redis queue service on found port
- **Database exposure**: Exposes MariaDB on port 3306

### Service Configuration
- **Docker Compose updates**: Modifies service port mappings
- **Service restart**: Restarts affected Docker services
- **Network validation**: Ensures services are accessible

### Config File Creation
- **Worker configs**: Creates `common_site_config.workers.json`
- **Site configs**: Creates `site_config.workers.json`
- **Redis URL**: Updates Redis queue URL to point to main server
- **Database host**: Updates database host to main server IP

## Configuration Files Created

### common_site_config.workers.json
```json
{
  "redis_queue": "redis://192.168.1.50:11000",
  // ... other existing config
}
```

### site_config.workers.json
```json
{
  "db_host": "192.168.1.50",
  // ... other existing config
}
```

## Network Requirements

### Ports Opened
- **Redis Queue**: Dynamic port (11000+) for background job queue
- **Database**: Port 3306 for MariaDB access

### Firewall Rules
Ensure the remote worker can access:
```bash
# Redis queue port (example)
iptables -A INPUT -p tcp --dport 11000 -s 192.168.1.100 -j ACCEPT

# Database port
iptables -A INPUT -p tcp --dport 3306 -s 192.168.1.100 -j ACCEPT
```

## Security Considerations

- **Limited access**: Only expose ports to specific remote worker IPs
- **SSH security**: Use SSH keys, disable password authentication
- **Database security**: Consider database user restrictions
- **Network isolation**: Use private networks where possible

## Troubleshooting

### Port Already in Use
The command automatically finds available ports. If all ports are busy:
```bash
# Check what's using ports
netstat -tulpn | grep :11000
```

### SSH Connection Failed
Verify SSH access:
```bash
ssh frappe@192.168.1.100 "echo 'Connection successful'"
```

### Service Restart Failed
Check Docker service status:
```bash
docker ps
docker logs CONTAINER_NAME
```

## Next Steps

After enabling remote worker:

1. **Sync workspace**: Use `remote-worker sync` command
2. **Test connectivity**: Verify worker can connect to main server
3. **Monitor services**: Check that background jobs are being processed

## See Also

- [remote-worker sync](sync.md) - Sync workspace to remote worker
- [Configuration Guide](../../configuration.md) - Remote worker configuration
