# Changelog

All notable changes to fmd will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `fmd release shell` — interactive shell inside a release's build container.
- `fmd release info` — inspect each app's git repo, branch, commit, and tag.
- `[switch] restore_db_from_site` — restore the database from another local FM
  site/bench at switch time, copying the source site's `encryption_key` into the target
  so Fernet-encrypted secrets stay decryptable.

### Changed
- `fmd info` is now `fmd release info`.
- The `[fm]` config section is merged into `[switch]` as `restore_db_from_site`.

### Removed
- `fmd maintenance` command — maintenance mode is now config-only via `[switch]`
  (`maintenance_mode` + `maintenance_mode_phases`); bypass tokens are gone.

## [0.1.0] - 2026-04-XX

### Added
- Initial release of fmd (Frappe Manager Deployer)
- Atomic release management with timestamped releases
- Zero-downtime deployment via symlink switching
- Pull mode: build on production server
- Ship mode: build locally, deploy to remote
- Frappe Cloud integration (apps, deps, DB sync)
- Worker draining before release switch
- Config-driven maintenance mode
- Remote worker support
- Monorepo app support with symlinks
- Automatic rollback on failure
- Release cleanup and retention management
- Database search-replace utility
- Comprehensive hook system (8 build hooks, 4 switch hooks)
- GitHub Actions integration (pull and ship strategies)
- TOML configuration with all options documented

### Dependencies
- Python >=3.13,<3.14
- Docker + Docker Compose v2
- Frappe Manager

[Unreleased]: https://github.com/rtcamp/fmd/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/rtcamp/fmd/releases/tag/v0.1.0
