# FAQ

## What is fmd?

fmd (Frappe Manager Deployer) layers zero-downtime deployments on top of an existing
Frappe Manager (FM) bench: atomic timestamped releases, instant rollback, and automated
migrations.

## How does fmd relate to Frappe Manager?

You need both. FM creates and manages the Frappe bench in Docker; fmd deploys versioned
releases on top of that bench. fmd requires an existing FM bench — it does not replace FM.

## Which Python version do I need?

Python >=3.13,<3.14. You also need Docker + Docker Compose v2.

## Can I use fmd on Windows?

Use WSL 2. fmd targets Linux and macOS.

## How do I access private GitHub repositories?

Set a GitHub token with `repo` scope, via environment or config:

```bash
export GITHUB_TOKEN=ghp_your_token_here
```

```toml
github_token = "ghp_your_token_here"
```

## What's the difference between pull and ship mode?

- **pull**: build on the target server and switch there (simplest; server needs build capacity).
- **ship**: build locally or in CI, rsync the release to the remote, then configure and switch there (offloads the build; remote needs SSH + rsync + uv).

See [Deploy modes](deploy-modes.md).

## What happens if a deployment fails?

The switch is atomic, so the site stays on the last working release. With `rollback = true`
in `[switch]`, fmd auto-reverts on switch failure; otherwise the failed release is kept
for debugging while the old one stays live.

## How many releases are kept?

`[release] releases_retain_limit` defaults to 7. Clean up manually with:

```bash
fmd cleanup mysite.localhost -r 3 -y
```

## Can I roll back to a previous release?

Yes, as long as it still exists:

```bash
fmd release list mysite.localhost
fmd release switch mysite.localhost release_YYYYMMDD_HHMMSS
```

## Can I sync from Frappe Cloud?

Yes. fmd can restore the latest FC database backup at switch time via
`[switch] use_fc_db = true`, and import an app list. fmd deploys to self-hosted
infrastructure; it syncs **from** FC, not **to** it. See [Configuration](configuration.md).

## How do I change a site's domain?

Use search-replace across the DB:

```bash
fmd search-replace mysite.localhost old.com new.com --dry-run
fmd search-replace mysite.localhost old.com new.com
```

## How do I enable debug logging?

Put `-v` before the subcommand:

```bash
fmd -v deploy pull --config site.toml
```

## Where can I get help?

- Docs: <https://rtcamp.github.io/fmd/>
- Issues: <https://github.com/rtcamp/fmd/issues>
- Discussions: <https://github.com/rtcamp/fmd/discussions>
