# FAQ

Frequently asked questions about fmd.

## General

### What is fmd?

fmd (Frappe Manager Deployer) is a zero-downtime deployment tool for Frappe applications. It provides atomic releases, instant rollback, and automated migrations.

### How does fmd relate to Frappe Manager?

fmd works **alongside** Frappe Manager (fm):

- **Frappe Manager**: Creates and manages Frappe benches in Docker
- **fmd**: Handles deployments with versioned releases on top of FM benches

You need both: FM for the runtime environment, fmd for deployment automation.

### What's the difference between FM and fmd?

| Feature | Frappe Manager (fm) | fmd |
|---------|---------------------|-----|
| Purpose | Development environment | Production deployment |
| Scope | Bench creation, Docker management | Release management, migrations, rollback |
| Target | Developers | DevOps, CI/CD pipelines |
| Deployment | Single bench state | Versioned releases with history |

### Can I use fmd without Frappe Manager?

No. fmd requires a Frappe Manager bench as the foundation. It extends FM with production deployment capabilities.

## Installation & Setup

### Which Python version do I need?

Python 3.10 or later. fmd is tested on Python 3.10, 3.11, 3.12, and 3.13.

### Do I need to install Docker?

Yes. fmd uses Docker containers (via Frappe Manager) to build and run Frappe applications.

### Can I use fmd on Windows?

fmd is designed for Linux and macOS. For Windows, use WSL 2 (Windows Subsystem for Linux).

### How do I access private GitHub repositories?

Set a GitHub personal access token:

```bash
export GITHUB_TOKEN=ghp_your_token_here
```

Or add to your config file:

```toml
github_token = "ghp_your_token_here"
```

## Deployment

### What's the difference between pull and ship mode?

- **Pull**: Build on production server, deploy locally (simpler, uses server resources)
- **Ship**: Build locally/CI, rsync to remote (offloads builds, enables parallel deploys)

See [Deploy Modes Guide](guides/deploy-modes.md) for details.

### How long does a deployment take?

**First deployment**: 8-15 minutes (downloads dependencies, builds apps)

**Subsequent deployments**: 3-6 minutes (uses cache, only rebuilds changed apps)

Actual time depends on:

- Number of apps
- Server resources (CPU, RAM, network)
- Cache hit rate

### Can I deploy to multiple servers at once?

Yes, with **ship mode**:

```bash
fmd deploy ship --config server1.toml
fmd deploy ship --config server2.toml
fmd deploy ship --config server3.toml
```

Build once, ship to multiple servers.

### Will deployment cause downtime?

**Minimal** (typically <1 second) during symlink switch.

Enable `maintenance_mode = true` for user-friendly maintenance page during migrations.

### What happens if deployment fails?

- If `rollback = true`: Automatically reverts to previous release
- If `rollback = false`: Site stays on previous working release, new release is kept for debugging

Either way, **your site stays up**.

## Release Management

### How many releases should I keep?

Default is 7. This balances:

- **Disk space**: Each release ~700 MB (Frappe + ERPNext)
- **Rollback options**: 7 releases = ~1-2 weeks of history

Adjust with:

```toml
[release]
releases_retain_limit = 7
```

### Can I rollback to any previous release?

Yes, as long as the release still exists (not cleaned up):

```bash
fmd release list mysite.localhost
fmd release switch mysite.localhost release_YYYYMMDD_HHMMSS
```

### What happens to old releases?

When you exceed `releases_retain_limit`, fmd automatically:

1. Backs up old releases to `deployment-backup/`
2. Deletes old releases from workspace

### Can I manually delete releases?

Yes:

```bash
fmd cleanup mysite.localhost -r 3 -y
```

Keeps 3 most recent releases, deletes the rest.

## Frappe Cloud Integration

### Can I sync from Frappe Cloud?

Yes. fmd can import:

- App list and commit hashes
- Python version
- Database backups

See [Frappe Cloud Sync Guide](guides/frappe-cloud.md).

### Does fmd work with Frappe Cloud?

fmd is for **self-hosted** deployments. It can sync **from** Frappe Cloud but doesn't deploy **to** Frappe Cloud.

Use case: Migrate from FC to self-hosted infrastructure.

### Do I need Frappe Cloud credentials?

Only if you want to sync from FC. For standard deployments, no FC account needed.

## Troubleshooting

### Build fails with "GitHub API rate limit exceeded"

Set a GitHub token:

```bash
export GITHUB_TOKEN=ghp_your_token_here
```

This increases rate limit from 60 to 5000 requests/hour.

### Migration fails during deployment

Check migration logs:

```bash
cat ~/frappe/sites/mysite/workspace/frappe-bench/.migrate_log
```

If rollback enabled, site automatically reverts to previous release.

### "Permission denied" errors

Never use `sudo` with fmd or pip. Use `uv tool` or `pipx` instead (user-space installation).

### Site not accessible after deployment

Check bench status:

```bash
fm info mysite
```

If stopped:

```bash
fm start mysite
```

### How do I enable debug logging?

```bash
fmd -v deploy pull --config site.toml
```

The `-v` flag must come **before** the subcommand.

## Advanced

### Can I customize the build process?

Yes, use hooks. Example:

```toml
[[apps]]
repo = "my-org/my-app"
ref = "main"
before_bench_build = """
npm ci
npm run build:prod
"""
```

See [Hooks Guide](guides/hooks.md) for details.

### Can I use monorepo apps?

Yes:

```toml
[[apps]]
repo = "my-org/monorepo"
ref = "main"
subdir_path = "apps/my-app"
```

See [Monorepo Apps Guide](guides/monorepo-apps.md).

### Can I run workers on separate servers?

Yes, use remote workers:

```bash
fmd remote-worker enable mysite.localhost --rw-server 192.168.1.100
```

See [Remote Workers Guide](guides/remote-workers.md).

### How do I change site domain?

Use search-replace:

```bash
fmd search-replace mysite.localhost "old.com" "new.com" --dry-run
fmd search-replace mysite.localhost "old.com" "new.com"
```

Then update site config and nginx.

### Can I deploy custom branches?

Yes:

```bash
fmd deploy pull mysite.localhost --app frappe/frappe:my-feature-branch
```

Or in config:

```toml
[[apps]]
repo = "frappe/frappe"
ref = "my-feature-branch"
```

## Getting Help

### Where can I get support?

- **Documentation**: [https://rtcamp.github.io/fmd/](https://rtcamp.github.io/fmd/)
- **GitHub Issues**: [https://github.com/rtcamp/fmd/issues](https://github.com/rtcamp/fmd/issues)
- **Discussions**: [https://github.com/rtcamp/fmd/discussions](https://github.com/rtcamp/fmd/discussions)

### How do I report a bug?

Open an issue: [https://github.com/rtcamp/fmd/issues/new](https://github.com/rtcamp/fmd/issues/new)

Include:

- fmd version (`fmd --version`)
- Full command and output
- Relevant logs
- Config file (remove secrets)

### How do I request a feature?

Start a discussion: [https://github.com/rtcamp/fmd/discussions/new](https://github.com/rtcamp/fmd/discussions/new)

### Is fmd production-ready?

fmd is actively developed and used in production by rtCamp. However, always test deployments in staging first.
