# Configuration Guide

Complete reference for configuring frappe-deployer deployments.

## Configuration Methods

frappe-deployer supports multiple configuration methods:

1. **TOML configuration files** (recommended)
2. **CLI arguments** (highest priority)
3. **Environment variables**
4. **Direct configuration content**

## Basic Configuration File

```toml
# config.toml
site_name = "my-site"
mode = "fm"  # or "host"
python_version = "3.10"
github_token = "ghp_xxxxxxxxxxxx"  # Optional for private repos

# App configurations
[[apps]]
repo = "frappe/frappe"
ref = "version-14"

[[apps]]
repo = "frappe/erpnext"  
ref = "version-14"
```

## Complete Configuration Schema

### Global Settings

```toml
# Required
site_name = "my-site-name"

# Deployment mode: "fm" or "host"
mode = "fm"

# Optional global settings
python_version = "3.10"
github_token = "ghp_xxxxxxxxxxxx"
verbose = false
uv = true  # Use UV package manager

# Release management
releases_retain_limit = 3
remove_remote = true
rollback = true

# Deployment features
maintenance_mode = true
run_bench_migrate = true
backups = true
configure = false
search_replace = false
```

### App Configuration

Apps are defined as an array of tables:

```toml
[[apps]]
repo = "frappe/frappe"
ref = "version-14"  # branch, tag, or commit hash

[[apps]]
repo = "myorg/custom_app"
ref = "main"
# Optional: app-specific build commands
fm_pre_build = "echo 'Pre-build setup for custom_app'"
fm_post_build = "echo 'Post-build cleanup for custom_app'"
```

### Custom Scripts

Execute shell scripts at different deployment stages:

```toml
# Host mode scripts (run on host system)
host_pre_script = '''
echo "Pre-deployment checks..."
systemctl status nginx
df -h
'''

host_post_script = '''
echo "Post-deployment tasks..."
systemctl reload nginx
curl -f http://localhost/api/method/ping
'''

# FM mode scripts (run in container)
fm_pre_script = '''
echo "Container pre-deployment..."
bench --version
'''

fm_post_script = '''
echo "Container post-deployment..."
bench migrate --site all
'''
```

### Mode-Specific Configuration

#### Host Mode Settings

```toml
mode = "host"

[host]
bench_path = "/home/frappe/bench"
```

#### FM Mode Settings

```toml
mode = "fm"

[fm]
restore_db_from_site = "source-site-name"  # Optional
```

### Remote Worker Configuration

```toml
[remote_worker]
server = "192.168.1.100"
ssh_user = "frappe"
ssh_port = 22
workspace_path = "/home/frappe/workspace"
include_dirs = ["custom_apps", "private_files"]
include_files = ["special_config.json"]
```

## GitHub Token Configuration

For private repositories, configure GitHub access:

### Method 1: Configuration File
```toml
github_token = "ghp_xxxxxxxxxxxx"
```

### Method 2: Environment Variable
```bash
export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"
frappe-deployer pull my-site-name --config-path config.toml
```

### Method 3: CLI Argument
```bash
frappe-deployer pull my-site-name \
  --github-token ghp_xxxxxxxxxxxx \
  --config-path config.toml
```

### Token Permissions

Your GitHub token needs:
- `repo` scope for private repositories
- `public_repo` scope for public repositories (if token is used)

## Environment Variables

All configuration options can be provided as environment variables using the pattern `FRAPPE_DEPLOYER_<OPTION>`:

```bash
export FRAPPE_DEPLOYER_SITE_NAME="my-site"
export FRAPPE_DEPLOYER_MODE="fm"
export FRAPPE_DEPLOYER_VERBOSE="true"
export FRAPPE_DEPLOYER_GITHUB_TOKEN="ghp_xxxxxxxxxxxx"
```

## CLI Configuration Override

CLI arguments have the highest priority and override all other settings:

```bash
# Config file has mode="host", but CLI overrides to FM
frappe-deployer pull my-site-name \
  --config-path config.toml \
  --mode fm \
  --verbose
```

## Direct Configuration Content

Pass configuration directly as a string:

```bash
frappe-deployer pull my-site-name \
  --config-content 'site_name="test"
mode="fm"
[[apps]]
repo="frappe/frappe"
ref="version-14"'
```

## App-Specific Build Commands

Customize the build process for individual apps:

```toml
[[apps]]
repo = "myorg/custom_app"
ref = "main"

# Commands run in FM container before app installation
fm_pre_build = '''
echo "Installing custom dependencies..."
apt-get update && apt-get install -y custom-package
npm install -g some-global-package
'''

# Commands run in FM container after app installation  
fm_post_build = '''
echo "Running post-install setup..."
bench --site all install-app custom_app
bench --site all execute custom_app.setup.setup_defaults
'''
```

## Configuration Validation

frappe-deployer validates your configuration:

- **Required fields**: `site_name` is mandatory
- **Mode validation**: Must be "fm" or "host"
- **App format**: Repository must be in "owner/repo" format
- **Path validation**: Paths must exist and be accessible

## Configuration Templates

### Development Environment
```toml
site_name = "dev-site"
mode = "fm"
python_version = "3.10"
verbose = true
maintenance_mode = false
backups = false

[[apps]]
repo = "frappe/frappe"
ref = "develop"

[[apps]]
repo = "frappe/erpnext"
ref = "develop"
```

### Production Environment
```toml
site_name = "production-site"
mode = "host"
python_version = "3.10"
releases_retain_limit = 5
maintenance_mode = true
backups = true
rollback = true

host_pre_script = '''
echo "Notifying monitoring systems..."
curl -X POST https://monitoring.example.com/api/deployment-start
'''

host_post_script = '''
echo "Deployment complete, running health checks..."
curl -f https://production-site.com/api/method/ping
'''

[[apps]]
repo = "frappe/frappe"
ref = "version-14"

[[apps]]
repo = "frappe/erpnext"
ref = "version-14"

[[apps]]
repo = "mycompany/custom_app"
ref = "v2.1.0"

[host]
bench_path = "/home/frappe/frappe-bench"
```

## Best Practices

1. **Version Control**: Keep configuration files in version control
2. **Environment Separation**: Use different configs for dev/staging/prod
3. **Token Security**: Use environment variables for GitHub tokens
4. **Validation**: Test configurations in development first
5. **Documentation**: Comment complex custom scripts

## Troubleshooting

**Configuration File Not Found**
```bash
# Use absolute paths
frappe-deployer pull my-site-name --config-path /full/path/to/config.toml
```

**GitHub Token Issues**
```bash
# Test token access
curl -H "Authorization: token ghp_xxxxxxxxxxxx" https://api.github.com/user
```

**Permission Errors**
```bash
# Ensure config file is readable
chmod 644 config.toml
```

## See Also

- [Quick Start](quick-start.md) - Basic configuration examples
- [Commands Reference](commands/) - Using configuration with commands
- [Examples](examples/) - Real-world configuration examples
