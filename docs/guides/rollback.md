# Rollback & Recovery

!!! info "Coming Soon"
    This guide is under development. Check back soon for complete documentation on rollback strategies and recovery workflows.

## What you'll learn

This guide will cover:

- **Instant rollback** — Switch to previous release in seconds
- **Automatic rollback** — On migration failure
- **Manual rollback** — When and how to rollback manually
- **Backup strategies** — Automatic backups before deployments
- **Database recovery** — Restore from backups
- **Disaster recovery** — Complete site recovery procedures

## Quick preview

Rollback to a previous release:

```bash
# List available releases
fmd release list mysite.localhost

# Rollback to specific release
fmd release switch mysite.localhost release_20260420_100000
```

Automatic rollback on failure:

```toml
[switch]
rollback = true
backups = true
```

## Rollback strategies

(Documentation in progress)

### Automatic rollback (recommended)

```toml
[switch]
rollback = true
```

If migrations fail, fmd automatically reverts to the previous working release.

### Manual rollback

When you need to rollback after a successful deployment:

```bash
fmd release list mysite.localhost
fmd release switch mysite.localhost release_YYYYMMDD_HHMMSS
```

### Disable rollback (debugging)

```toml
[switch]
rollback = false
```

Failed deployments stay on previous release, new release preserved for debugging.

## Backup strategies

(Documentation in progress)

### Automatic backups

```toml
[switch]
backups = true
backup_retention = 5
```

### Manual backups

Before major changes:

```bash
# Via Frappe Manager
fm backup mysite
```

## Recovery workflows

(Documentation in progress)

### Scenario 1: Migration failed
→ Automatic rollback (if enabled)

### Scenario 2: Code bug discovered post-deployment
→ Manual rollback to previous release

### Scenario 3: Data corruption
→ Database restore from backup

### Scenario 4: Complete site failure
→ Disaster recovery procedure

## Release retention

(Documentation in progress)

```toml
[release]
releases_retain_limit = 7
```

Old releases are automatically moved to `deployment-backup/` directory.

## Next steps

For now, see the [Concepts Guide](../reference/concepts.md#release-lifecycle) for release lifecycle details.
