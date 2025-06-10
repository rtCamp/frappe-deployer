# Installation Guide

## Requirements

- Python 3.8 or higher
- Git
- Access to Frappe repositories (GitHub token for private repos)

### System Requirements

**For Host Mode:**
- Direct access to Frappe bench directory
- Python virtual environment capabilities
- Sufficient disk space for releases and backups

**For FM Mode:**
- Docker and Docker Compose
- Frappe Manager installed and configured
- Container orchestration permissions

## Installation Methods

### Using pip (Recommended)

```bash
pip install frappe-deployer
```

### From Source

```bash
git clone https://github.com/your-org/frappe-deployer.git
cd frappe-deployer
pip install -e .
```

## Verification

Verify installation by checking the version:

```bash
frappe-deployer --version
```

## Initial Setup

After installation, you'll need to:

1. **Configure your first site** - See [Quick Start Guide](quick-start.md)
2. **Set up GitHub token** (if using private repositories) - See [Configuration Guide](configuration.md#github-token)
3. **Choose deployment mode** - See [Deployment Modes](deployment-modes.md)

## Next Steps

- [Quick Start Tutorial](quick-start.md) - Get your first deployment running
- [Core Concepts](concepts.md) - Understand the architecture
- [Configuration Guide](configuration.md) - Set up your deployment
