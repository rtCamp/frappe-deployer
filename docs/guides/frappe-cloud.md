# Frappe Cloud Sync

!!! info "Coming Soon"
    This guide is under development. Check back soon for complete documentation on syncing from Frappe Cloud to self-hosted deployments.

## What you'll learn

This guide will cover:

- **App list sync** — Import exact app versions from your FC site
- **Python version matching** — Use the same Python version as FC
- **Database migration** — Download and restore FC backups
- **Configuration sync** — Match FC site configuration
- **Migration workflow** — Complete FC → self-hosted migration guide

## Quick preview

fmd can import your Frappe Cloud site configuration:

```toml
[fc]
api_key = "your-fc-api-key"
api_secret = "your-fc-api-secret"
site_name = "mysite.frappe.cloud"
team_name = "my-team"
```

Then deploy with FC sync:

```bash
fmd deploy pull --config site.toml \
  --fc-use-apps \
  --fc-use-deps \
  --fc-use-db
```

## What gets synced

(Documentation in progress)

- ✅ App repository URLs and commit hashes
- ✅ Python version
- ✅ Database backups (latest or specific date)
- ⚠️ Site configuration (partial — review after migration)
- ❌ File uploads (manual rsync required)
- ❌ Custom SSL certificates (reconfigure after migration)

## Migration checklist

(Documentation in progress)

1. Set up FC API credentials
2. Run first deployment with `--fc-use-apps --fc-use-deps`
3. Test the deployment
4. Schedule downtime
5. Run final deployment with `--fc-use-db`
6. Update DNS records
7. Verify site functionality

## Next steps

For now, see the [Configuration Guide](configuration.md#frappe-cloud-integration) for FC credential setup.
