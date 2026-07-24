# Deploy Modes

fmd deploys in two ways: **pull** and **ship**. Both produce the same immutable,
timestamped release and atomic symlink switch (see [Concepts](concepts.md)); they differ
only in *where the build runs* and *what the target server must provide*.

| Mode | Build location | Deploy target | When to use |
|------|----------------|---------------|-------------|
| pull | The target server | Same server | Target has build capacity and git/registry access; simplest setup |
| ship | Local machine or CI (Docker runner image) | Remote via SSH + rsync | Offload the build; target should stay lean (SSH + rsync + uv only) |

## Pull

Build on the target server and switch there in one step.

```bash
fmd deploy pull mysite.localhost \
  --app frappe/frappe:version-15 \
  --app frappe/erpnext:version-15
```

Or drive everything from config:

```bash
fmd deploy pull --config site.toml
```

`deploy pull` runs `release configure` (if the bench is not yet in fmd layout), then
`release create` and `release switch` on the target. Because the build happens locally on
that server, it needs enough CPU/RAM to build inside Docker plus network access to git and
any container registries it pulls from.

Pull needs no `[ship]` section and no SSH configuration — you are already on the box.

## Ship

Build locally or in CI, then hand the finished artifacts to a lean remote.

```bash
fmd deploy ship --config site.toml
```

`deploy ship` requires a `[ship]` section and proceeds in four phases:

1. **Build** — `release create` runs in Docker (the fmd runner image) on your local
   machine or CI runner, producing an immutable `release_YYYYMMDD_HHMMSS/` directory.
2. **Transfer** — the release and its config snapshot are `rsync`-ed to the remote.
3. **Configure** — `release configure` runs on the remote via `uvx`, wiring the bench
   layout around the pre-built artifacts (no git access needed).
4. **Switch** — `release switch` runs on the remote via `uvx` to activate the release
   atomically (backup / migrate / maintenance behavior per `[switch]`).

The remote only needs **SSH**, **rsync**, and **uv** — fmd itself is fetched and run there
via `uvx`, so no build toolchain or git access is required on the target.

### `[ship]` configuration

```toml
[ship]
host = "203.0.113.10"          # remote SSH host
ssh_user = "frappe"            # default: frappe
ssh_port = 22                  # default: 22
remote_path = ""               # empty = auto-detect $HOME/frappe/sites/<site>
fmd_source = ""                # git URL/local path to run fmd via uvx; empty = auto
rsync_options = []             # extra rsync flags
```

See `example-config.toml` at the repo root for the fully annotated schema, and
[Configuration](configuration.md) for how `[ship]` fits with the rest of the config.

## Choosing a mode

- Prefer **pull** when the target server can build (adequate CPU/RAM, git/registry access)
  and you want the simplest path — one command, no SSH plumbing.
- Prefer **ship** when you want to keep the target lean, build on a beefier CI runner or
  local machine, or deploy the same pre-built release to more than one server.

Ship builds once and can reuse the same release across multiple targets by pointing
different `[ship]` configs at it.

## Next steps

- Automate either mode with [GitHub Actions](github-actions.md).
- Understand releases and the symlink switch in [Concepts](concepts.md).
- Tune switch behavior and app builds in [Configuration](configuration.md).
