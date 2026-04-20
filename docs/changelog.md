# Changelog

All notable changes to fmd will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive documentation site with MkDocs Material theme
- Getting Started guides (requirements, installation, quick start)
- Deployment mode guides (pull vs ship)
- Configuration reference
- Command reference
- FAQ and troubleshooting

### Changed
- Documentation restructured to match Frappe Manager layout

## [0.1.0] - 2026-04-XX

### Added
- Initial release of fmd (Frappe Manager Deployer)
- Atomic release management with timestamped releases
- Zero-downtime deployment via symlink switching
- Pull mode: build on production server
- Ship mode: build locally, deploy to remote
- Frappe Cloud integration (apps, deps, DB sync)
- Worker draining before release switch
- Maintenance mode with bypass tokens
- Remote worker support
- Monorepo app support with symlinks
- Automatic rollback on failure
- Release cleanup and retention management
- Database search-replace utility
- Comprehensive hook system (8 build hooks, 4 switch hooks)
- GitHub Actions integration (pull and ship strategies)
- TOML configuration with all options documented

### Dependencies
- Python 3.10+
- Docker + Docker Compose V2
- Frappe Manager

---

## Release Notes

### Version 0.1.0

First public release of fmd, bringing production-grade deployment capabilities to Frappe Manager benches.

**Key Features:**

- **Atomic Releases**: Every deployment creates a timestamped release, activated instantly via symlinks
- **Zero Downtime**: Workers drain gracefully, maintenance mode only during migrations
- **Two Deploy Modes**: Pull (on-server build) and ship (local build + rsync to remote)
- **Frappe Cloud Sync**: Import apps, Python deps, and database backups from Frappe Cloud
- **Smart Rollback**: Automatic rollback on migration failures, instant manual rollback to any previous release
- **Flexible Hooks**: Customize every phase of build and deployment with shell scripts
- **CI/CD Ready**: GitHub Actions integration with dedicated action

**Breaking Changes:**

None (initial release)

**Migration Guide:**

For new installations, follow the [Quick Start Guide](getting-started/quick-start.md).

---

## Upcoming Features

See [GitHub Issues](https://github.com/rtcamp/fmd/issues) and [Discussions](https://github.com/rtcamp/fmd/discussions) for planned features and community requests.

**Potential roadmap:**

- Blue-green deployment strategy
- Canary deployments
- Health checks before switch
- Slack/Discord notifications
- Pre-built Docker images for faster ship mode
- Multi-site deployments
- Integration with monitoring tools

---

## Contributing

Found a bug or have a feature request? Open an issue or discussion on [GitHub](https://github.com/rtcamp/fmd).

---

[Unreleased]: https://github.com/rtcamp/fmd/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/rtcamp/fmd/releases/tag/v0.1.0
