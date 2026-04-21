# Deploy Modes

fmd supports two deployment strategies: **pull** and **ship**. Each has different use cases and tradeoffs.

## Overview

| Mode  | Build Location    | Deploy Target     | When to Use                                     |
|-------|-------------------|-------------------|-------------------------------------------------|
| pull  | Production server | Same server       | Standard deployments, server has build capacity |
| ship  | CI runner/local   | Remote via SSH    | Offload builds, cross-arch, multi-server deploy |

## Pull Mode

**Build on the production server, deploy on the same server.**

!!! tip "When to Choose Pull Mode"
    Pull mode is ideal when your production server has adequate CPU/RAM for builds (4+ cores, 8+ GB RAM) and you value simplicity over build isolation. For resource-constrained servers or multi-server deployments, consider ship mode instead.

### How It Works

1. Connect to production server where Frappe Manager bench exists
2. Run `fmd deploy pull` directly on the server
3. fmd creates a new release by building inside Docker on that server
4. Switch to new release atomically

### Usage

```bash
fmd deploy pull mysite.localhost \
  --app frappe/frappe:version-15 \
  --app frappe/erpnext:version-15 \
  --maintenance-mode --backups
```

Or with a config file:

```bash
fmd deploy pull --config site.toml
```

### Advantages

- **Simple setup**: No SSH configuration needed
- **Direct control**: Run commands directly on production
- **Immediate feedback**: See build logs in real-time
- **No file transfer**: Everything happens locally

### Disadvantages

- **Server resource usage**: Build consumes CPU/RAM on production
- **Potential downtime**: Heavy builds can affect running services
- **Sequential only**: Can't deploy to multiple servers in parallel
- **Architecture-specific**: Must build on same arch as production

### When to Use Pull

- Small to medium deployments
- Server has enough CPU/RAM to build without affecting services
- Single-server setup
- You have direct SSH access to production

### Example: Pull from CI

Even in CI, you can SSH to production and run pull:

```yaml
- name: Deploy via pull
  run: |
    ssh user@prod "cd /path/to/bench && \
      fmd deploy pull --config site.toml"
```

## Ship Mode

**Build locally or in CI, then ship to remote production server.**

!!! tip "When to Choose Ship Mode"
    Ship mode excels in three scenarios: (1) deploying to multiple servers from a single build, (2) offloading builds from resource-constrained production servers, and (3) cross-architecture deployments (e.g., build on x86, deploy to ARM). The tradeoff is more complex setup with SSH keys and rsync configuration.

### How It Works

Ship mode coordinates a multi-step deployment workflow:

#### 1. Local Build Phase
- Runs `fmd release create` in Docker on CI runner/local machine
- Pulls runner image (e.g., `ghcr.io/rtcamp/fmd-runner:latest`)
- Installs Python dependencies via uv
- Installs Node.js dependencies  
- Builds production assets (JS, CSS)
- Creates immutable release directory: `workspace/release_YYYYMMDD_HHMMSS/`

#### 2. Transfer Phase
- Rsyncs entire release directory to remote server
- Transfers TOML config file
- Ensures remote has uv/uvx installed for running fmd

#### 3. Remote Configuration Phase
- Runs `fmd release configure` on remote via uvx
- Creates bench directory structure if not exists
- Symlinks apps into bench
- No git access required (uses pre-built artifacts)

#### 4. Remote Switch Phase  
- Runs `fmd release switch` to activate new release
- Updates `workspace/frappe-bench` symlink to new release
- Optionally drains workers, enables maintenance mode
- Runs migrations if configured
- Takes backups if configured
- Restarts services

**Key insight**: Ship builds locally but delegates configuration/switch to remote fmd instance via uvx.

### Usage

Requires a `[ship]` section in your config:

```toml
[ship]
server_ip = "192.168.1.100"
ssh_user = "frappe"
ssh_port = 22
remote_workspace_root = "/home/frappe/frappe/sites/mysite.localhost/workspace"
```

Then deploy:

```bash
fmd deploy ship --config site.toml
```

### Advantages

- **Offload builds**: Free up production resources
- **Parallel deploys**: Ship same release to multiple servers
- **Cross-architecture**: Build on x86, deploy to ARM (or vice versa)
- **Faster deploys**: Rsync is faster than rebuilding on each server
- **Pre-validated**: Test release locally before shipping

### Disadvantages

- **Complex setup**: Requires SSH keys, rsync, proper permissions
- **Network dependency**: Large file transfer over network
- **Initial slowness**: First build downloads all dependencies
- **Storage overhead**: Need disk space on both machines

### When to Use Ship

- Multiple production servers (deploy once, ship to many)
- Limited production resources (small VPS, shared hosting)
- Cross-architecture deployments
- Want to test release locally before production
- CI/CD pipeline with powerful runners

### Example: Ship from GitHub Actions

```yaml
- name: Deploy via ship
  uses: rtcamp/frappe-deployer@main
  with:
    command: ship
    config_path: .github/configs/site.toml
    gh_token: ${{ secrets.GH_TOKEN }}
    ssh_private_key: ${{ secrets.SSH_PRIVATE_KEY }}
```

See [GitHub Actions Guide](github-actions.md) for complete setup.

## Hybrid Approach

You can mix modes:

- **Development**: Use pull mode on staging server
- **Production**: Use ship mode for controlled releases

Or:

- **Regular deploys**: Use pull for convenience
- **Emergency deploys**: Use ship to build on powerful local machine

## Performance Comparison

### Build Time (Frappe + ERPNext, 4-core server)

| Mode | First Build | Subsequent | Notes |
|------|-------------|------------|-------|
| pull | ~8-12 min   | ~3-5 min   | Uses `.cache` on server |
| ship | ~10-15 min  | ~4-6 min   | Initial download, then rsync delta |

### Network Transfer (ship mode)

| Release Content | Size | Transfer Time (1 Gbps) |
|-----------------|------|------------------------|
| Apps + venv     | ~500 MB | ~4-5 seconds |
| Node modules    | ~200 MB | ~2 seconds |
| Built assets    | ~50 MB  | <1 second |
| **Total**       | ~750 MB | ~7-10 seconds |

Subsequent deploys transfer only changed files (much smaller).

## Choosing a Mode

Use this decision tree:

```
Do you have multiple production servers?
├─ YES → Use ship (build once, deploy to all)
└─ NO → Does production server have >4 CPU cores and >8 GB RAM?
    ├─ YES → Use pull (simpler)
    └─ NO → Use ship (offload builds)
```

## Advanced: Custom Build Server

You can designate a dedicated build server:

1. **Build server**: Runs fmd in ship mode, builds releases
2. **Production servers**: Receive releases via rsync, only run switch

This separates concerns:

- Build server handles dependency downloads, compilations
- Production servers only run application code

Example workflow:

```bash
# On build server
fmd deploy ship --config server1.toml
fmd deploy ship --config server2.toml
fmd deploy ship --config server3.toml
```

All three servers receive the same pre-built release.

## Next Steps

- Learn about [GitHub Actions](github-actions.md) integration
- Configure [hooks](hooks.md) to customize build process
- Understand [release lifecycle](../reference/concepts.md)
