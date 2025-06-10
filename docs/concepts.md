# Core Concepts

Understanding the key concepts behind frappe-deployer will help you use it effectively.

## Deployment Modes

### Frappe Manager (FM) Mode
- **Container-based**: Uses Docker containers for isolation
- **Built-in services**: Database, Redis, and other services managed automatically
- **Simplified setup**: Minimal host configuration required
- **Best for**: Development, staging, and containerized production environments

### Host Mode
- **Direct installation**: Apps installed directly on the host system
- **Manual services**: You manage database, Redis, and other services
- **More control**: Direct access to all system components
- **Best for**: Traditional production deployments, custom configurations

## Directory Structure

frappe-deployer organizes deployments using a structured approach:

```
./                              # Your project root
├── deployment-data/            # Persistent data directory
│   ├── sites/                  # Site files and databases
│   ├── config/                 # Configuration files
│   ├── logs/                   # Application logs
│   └── apps/                   # App-specific data
├── deployment-backup/          # Backup storage
│   ├── releases/               # Release backups
│   └── databases/              # Database backups
└── release_YYYYMMDD_HHMMSS/   # Current release directory
    ├── apps/                   # Installed applications
    ├── sites -> ../deployment-data/sites  # Symlinked to data
    └── ...                     # Other bench files
```

### Key Directories

- **deployment-data/**: Persistent data that survives deployments
- **deployment-backup/**: Automatic backups for rollback capability  
- **release_YYYYMMDD_HHMMSS/**: Timestamped release directories
- **Current symlink**: Points to the active release

## Release Management

### Release Creation
Each deployment creates a new timestamped release:
- Format: `release_YYYYMMDD_HHMMSS`
- Example: `release_20231201_143022`
- Independent: Each release is self-contained

### Symlink Management
- **bench_path**: Always points to current release
- **Data directories**: Symlinked from release to deployment-data
- **Atomic switches**: Deployments are atomic operations

### Rollback Capability
- Previous releases preserved based on retention policy
- Quick rollback by switching symlinks
- Backup restoration for data recovery

## Configuration Hierarchy

Settings are applied in order of precedence:

1. **CLI arguments** (highest priority)
2. **Environment variables**
3. **TOML configuration file**
4. **Default values** (lowest priority)

This allows flexible overrides for different environments.

## App Management

### Repository Specification
Apps are specified as `owner/repo:ref`:
- `frappe/frappe:version-14` - Specific branch/tag
- `myorg/custom_app:main` - Latest main branch
- `local/app:HEAD` - Local development

### Build Process
1. **Clone**: Repository cloned to release directory
2. **Install**: Python dependencies installed
3. **Build**: App-specific build commands executed
4. **Migrate**: Database schema updates applied

## Backup Strategy

### Automatic Backups
- **Before deployment**: Current state backed up
- **Configurable retention**: Keep N releases/backups
- **Compressed storage**: Efficient disk usage

### Backup Types
- **Release backups**: Complete release directory
- **Database backups**: Site databases with compression
- **Configuration backups**: Settings and customizations

## Security Considerations

### GitHub Tokens
- Required for private repositories
- Scoped to repository access only
- Can be provided via config file or environment variable

### Maintenance Mode
- **Developer bypass**: Tokens generated for development access
- **User-friendly pages**: Custom maintenance pages served
- **Automatic management**: Enabled during deployment, disabled after

## Performance Optimization

### UV Package Manager
- **Faster installs**: Rust-based package manager
- **Better caching**: Improved dependency resolution
- **Optional**: Falls back to pip if unavailable

### Parallel Operations
- **Concurrent downloads**: Multiple repositories cloned simultaneously
- **Optimized builds**: Efficient resource utilization
- **Progress tracking**: Real-time feedback during operations

## Next Steps

- **[Quick Start](quick-start.md)**: Get hands-on experience
- **[Configuration](configuration.md)**: Set up your deployment
- **[Deployment Modes](deployment-modes.md)**: Choose the right mode
- **[Commands](commands/)**: Learn available operations
