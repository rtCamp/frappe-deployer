# Frappe Deployer

A CLI tool for managing and deploying Frappe applications with support for both host and Frappe Manager (FM) modes.

## Key Features

- **Dual Deployment Modes**: Host and Frappe Manager (FM) support
- **Release Management**: Timestamped releases with rollback capability
- **Backup & Restore**: Automated backups with compression and retention policies
- **Database Operations**: Cross-site migration and search/replace functionality
- **Custom Scripts**: Pre/post deployment hooks for custom automation
- **Remote Workers**: Distributed deployment across multiple servers
- **Maintenance Mode**: Built-in maintenance pages with developer bypass

## Quick Start

```bash
# Install frappe-deployer (installation instructions in docs/installation.md)

# Configure a new site
frappe-deployer configure my-site-name --mode fm --backups

# Deploy Frappe and ERPNext
frappe-deployer pull my-site-name \
  -a frappe/frappe:version-15 \
  -a frappe/erpnext:version-15 \
  --maintenance-mode
```

## Documentation

- **[Getting Started](docs/quick-start.md)** - 5-minute tutorial
- **[Installation Guide](docs/installation.md)** - Setup and requirements
- **[Configuration Reference](docs/configuration.md)** - Complete TOML configuration
- **[Command Reference](docs/commands/)** - All available commands
- **[Examples & Recipes](docs/recipes/)** - Real-world use cases

## Installation

```bash
# Installation methods will be documented in docs/installation.md
pip install git+ssh@github.com:rtcamp/frappe-deployer
```

## Support

- **Documentation**: [docs/](docs/)
- **Troubleshooting**: [docs/troubleshooting.md](docs/troubleshooting.md)
- **Examples**: [docs/examples/](docs/examples/)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

[License information]
