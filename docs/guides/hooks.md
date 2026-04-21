# Hooks & Lifecycle

!!! info "Coming Soon"
    This guide is under development. Check back soon for complete documentation on customizing build and deployment lifecycle with hooks.

## What you'll learn

This guide will cover:

- **Pre and post hooks** for each deployment phase
- **Shell script hooks** for custom build steps
- **Asset building** with hooks (Webpack, Vite, custom tools)
- **Testing automation** with pre-switch hooks
- **Notification hooks** for Slack, email, webhooks
- **Environment-specific hooks** (local vs remote)

## Quick preview

Hooks allow you to run custom shell commands at specific points in the deployment lifecycle:

```toml
[[apps]]
repo = "my-org/my-app"
ref = "main"
before_bench_build = """
npm ci
npm run build:prod
"""
after_bench_build = """
echo "Build completed at $(date)"
"""
```

## Available hook points

(Documentation in progress)

- `before_bench_build`
- `after_bench_build`
- `before_switch`
- `after_switch`
- `on_failure`

## Common use cases

(Documentation in progress)

### Build frontend assets
### Run tests before deployment
### Send notifications
### Database migrations
### Cache warming

## Next steps

For now, see the inline examples in [Configuration Guide](configuration.md#hooks) and the [example-config.toml](https://github.com/rtcamp/fmd/blob/main/example-config.toml).
