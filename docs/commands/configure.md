# configure Command

Sets up initial deployment configuration by moving existing bench to data directory structure.

## Synopsis

```bash
frappe-deployer configure SITE_NAME [OPTIONS]
```

## Description

The `configure` command prepares your workspace for frappe-deployer by:

1. Creating the deployment directory structure
2. Moving existing bench files to `deployment-data/`
3. Setting up symlinks between release and data directories
4. Initializing backup directories

## Arguments

- `SITE_NAME` - Name of the site to configure (required)

## Options

### Configuration
- `--config-path PATH` - Path to TOML configuration file
- `--config-content TEXT` - Direct configuration content as string

### Mode Selection
- `--mode {fm,host}` - Deployment mode (default: fm)
- `--host-bench-path PATH` - Bench path for host mode
- `--python-version VERSION` - Python version to use

### Features  
- `--backups / --no-backups` - Enable/disable backup functionality (default: enabled)
- `--verbose` - Enable detailed output

## Examples

### Basic Configuration

```bash
# Configure with TOML file
frappe-deployer configure my-site-name --config-path ./config.toml

# Configure FM mode with backups
frappe-deployer configure my-site-name --mode fm --backups

# Configure host mode
frappe-deployer configure my-site-name \
  --mode host \
  --host-bench-path /home/frappe/bench \
  --python-version 3.10
```

### Configuration with TOML File

```toml
# config.toml
site_name = "my-site"
mode = "fm"
python_version = "3.10"
backups = true

[fm]
# FM-specific settings

[host]
bench_path = "/home/frappe/bench"
```

```bash
frappe-deployer configure my-site-name --config-path config.toml
```

## What Gets Created

After running configure, your directory structure will be:

```
./
├── deployment-data/           # Created - persistent data
│   ├── sites/                 # Moved from existing bench
│   ├── config/               
│   └── logs/
├── deployment-backup/         # Created - backup storage
└── [existing bench files moved to deployment-data/]
```

## Configuration File Integration

The configure command can read settings from TOML files. CLI options override file settings.

Priority order:
1. CLI arguments (highest)
2. Configuration file
3. Defaults (lowest)

## Next Steps

After configuration:

1. **Deploy apps**: Use [`pull` command](pull.md)
2. **Set up backups**: Configure retention policies
3. **Test deployment**: Verify everything works

## Troubleshooting

**Permission Errors**
```bash
# Ensure proper ownership
sudo chown -R $USER:$USER ./deployment-data/
```

**Existing Bench Conflicts**
- The command will move existing bench files safely
- Original structure is preserved in deployment-data/
- Use `--verbose` to see what's being moved

**Mode Selection**
- Choose `fm` for containerized environments  
- Choose `host` for traditional server deployments
- See [Deployment Modes](../deployment-modes.md) for guidance

## See Also

- [pull command](pull.md) - Deploy applications after configuration
- [Configuration Guide](../configuration.md) - Complete configuration reference
- [Deployment Modes](../deployment-modes.md) - Choose the right mode
