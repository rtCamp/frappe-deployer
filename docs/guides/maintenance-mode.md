# Maintenance Mode

!!! info "Coming Soon"
    This guide is under development. Check back soon for complete documentation on maintenance mode and bypass tokens.

## What you'll learn

This guide will cover:

- **Automatic maintenance mode** during deployments
- **Manual maintenance control** with `fmd maintenance enable/disable`
- **Bypass tokens** for developer access during maintenance
- **Custom maintenance pages** with branding
- **Maintenance mode behavior** during migrations vs regular deployments

## Quick preview

Enable maintenance mode automatically during deployment:

```toml
[switch]
maintenance_mode = true
```

Or control it manually:

```bash
fmd maintenance enable mysite.localhost
fmd maintenance disable mysite.localhost
fmd maintenance token mysite.localhost
```

## How it works

(Documentation in progress)

When maintenance mode is enabled:

- Users see a maintenance page (customizable)
- Frappe workers drain gracefully (configurable timeout)
- Migrations run safely without user traffic
- Developers can bypass with a token
- Mode disables automatically after successful deployment

## Maintenance strategies

(Documentation in progress)

### Zero-downtime deployments
Skip maintenance mode for code-only changes:

```toml
[switch]
maintenance_mode = false
migrate = false
```

### Safe migration deployments
Enable maintenance for database changes:

```toml
[switch]
maintenance_mode = true
migrate = true
```

### Planned maintenance
Manual control for scheduled maintenance windows.

## Next steps

For now, see the [Configuration Guide](configuration.md#switch-behavior) for maintenance mode options.
