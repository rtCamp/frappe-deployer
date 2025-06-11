# remote-worker

Manage remote worker deployments for distributed Frappe setups.

## Available Commands

- [`enable`](enable.md) - Enable remote worker configuration
- [`sync`](sync.md) - Sync workspace to remote worker

## Overview

Remote workers allow you to distribute Frappe background jobs across multiple servers while keeping the main application server separate. This is useful for:

- **Load distribution**: Separate heavy background tasks from web requests
- **Scalability**: Add more worker capacity as needed
- **Isolation**: Keep long-running jobs away from user-facing services

## Architecture

```
Main Server                    Remote Worker Server
├── Web Services              ├── Background Workers
├── Database                  ├── Queue Processors  
├── Redis Queue (exposed)     ├── Scheduled Jobs
└── File Storage              └── Worker Services
```

## Prerequisites

- **FM mode only**: Remote workers currently only support FM deployments
- **SSH access**: Passwordless SSH access to remote worker servers
- **Docker**: Docker and Docker Compose on both servers
- **Network**: Redis queue port (typically 11000+) accessible between servers

## Quick Start

1. **Enable remote worker**:
   ```bash
   frappe-deployer remote-worker enable my-site --server 192.168.1.100
   ```

2. **Sync workspace**:
   ```bash
   frappe-deployer remote-worker sync my-site --server 192.168.1.100
   ```

## Configuration

Remote workers can be configured via TOML:

```toml
[remote_worker]
server = "192.168.1.100"
ssh_user = "frappe"
ssh_port = 22
workspace_path = "/home/frappe/workspace"
include_dirs = ["custom_apps", "private_files"]
include_files = ["special_config.json"]
```

## Security Considerations

- **SSH keys**: Use SSH key authentication, not passwords
- **Firewall**: Limit Redis queue port access to trusted IPs
- **Network**: Consider VPN or private networks for production
- **Database**: Ensure database access is properly secured

## Limitations

- **FM mode only**: Host mode not currently supported
- **Single worker**: Each site supports one remote worker server
- **File sync**: Large files may slow sync operations
- **Network dependent**: Requires stable network connection

## See Also

- [Configuration Guide](../../configuration.md) - Remote worker configuration
- [pull command](../pull.md) - Main deployment workflow
