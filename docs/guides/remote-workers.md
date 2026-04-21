# Remote Workers

!!! info "Coming Soon"
    This guide is under development. Check back soon for complete documentation on distributed worker setups.

## What you'll learn

This guide will cover:

- **Remote worker architecture** — Separate web and worker servers
- **Initial setup** — Configure remote worker servers
- **Release synchronization** — Keep workers in sync with web server
- **Worker drain** — Graceful task completion before release switch
- **Troubleshooting** — Common remote worker issues
- **Multi-region deployments** — Workers in different locations

## Quick preview

Enable and sync remote workers:

```bash
# Enable remote worker
fmd remote-worker enable mysite.localhost --rw-server 192.168.1.100

# Sync release to worker
fmd remote-worker sync mysite.localhost --rw-server 192.168.1.100
```

## Architecture overview

(Documentation in progress)

```
┌─────────────┐         ┌─────────────┐
│  Web Server │         │Worker Server│
│  (Primary)  │────────▶│  (Remote)   │
│             │  rsync  │             │
│ fmd release │         │ fmd release │
└─────────────┘         └─────────────┘
```

- **Web server** runs web processes and Frappe bench
- **Worker server** runs background workers only
- **Releases sync** automatically during deployment
- **Workers drain** before release switch

## Setup steps

(Documentation in progress)

1. Install fmd on remote worker server
2. Configure SSH access between servers
3. Run `fmd remote-worker enable`
4. Deploy normally — workers sync automatically

## Configuration

(Documentation in progress)

```toml
[remote_workers]
servers = ["192.168.1.100", "192.168.1.101"]
ssh_user = "frappe"
ssh_port = 22
drain_timeout = 300
```

## Next steps

For now, see the [Commands Reference](../commands/remote-worker.md) for available remote-worker commands.
