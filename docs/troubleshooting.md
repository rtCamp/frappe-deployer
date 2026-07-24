# Troubleshooting

Common fmd-specific issues and fixes. For more detail on any command, run
`fmd <command> --help`, and re-run with verbose logging (see below) to see what fmd is
doing.

## Verbose logs

Add `-v` **before** the subcommand to get detailed logs:

```bash
fmd -v deploy pull --config site.toml
```

This is the first thing to try for almost any failure.

## Private repository access

Cloning private app repos during the build fails without a token:

```
ERROR: Repository access denied
```

Set a GitHub token with `repo` scope, via config or environment:

```toml
github_token = "ghp_xxx"
```

```bash
export GITHUB_TOKEN=ghp_xxx
fmd deploy pull --config site.toml

# Test the token
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
```

## Config validation / invalid TOML

Config errors are usually a TOML syntax problem. Validate the file directly:

```bash
python3 -c "import tomllib; tomllib.load(open('site.toml', 'rb'))"
```

Common mistakes:

- Missing quotes: `repo = frappe/frappe` (wrong) vs `repo = "frappe/frappe"` (correct)
- `[[apps]` instead of `[[apps]]`
- Unescaped backslashes in Windows paths

## Frappe Cloud credentials

FC sync fails with auth errors when credentials or names are wrong. Verify API access and
that the names match exactly:

```bash
curl -u fc_key:fc_secret \
  https://frappecloud.com/api/method/press.api.bench.apps
```

```toml
[fc]
api_key = "..."
api_secret = "..."
site_name = "mysite.frappe.cloud"   # must match the FC site name
team_name = "my-team"               # optional; must match the FC team slug
```

## Symlink / monorepo app not found

A monorepo app fails to build:

```
ERROR: Subdir path 'apps/my-app' not found in repo
```

The `subdir_path` must exist in the repo at the given `ref`, and `symlink = true` is
required for subdir apps:

```toml
[[apps]]
repo = "my-org/monorepo"
ref = "main"
subdir_path = "apps/my-app"   # must exist at this ref
symlink = true
```

Verify the path exists in the repo before deploying.

## Worker drain timeouts

If workers don't finish their jobs within the drain window during a switch, raise the
timeouts in `[switch]`:

```toml
[switch]
drain_workers = true
drain_workers_timeout = 900   # default 300
worker_kill_timeout = 30      # force-kill after this
```

For critical background jobs, confirm workers are idle before deploying:

```bash
# FM mode
docker exec -it <container> supervisorctl status

# Host mode
supervisorctl status | grep rq
```

## Inspecting the current release

To see which release is live and what each app was built from:

```bash
fmd release list mysite.localhost
fmd release info mysite.localhost
readlink ~/frappe/sites/mysite.localhost/workspace/frappe-bench
```

The switch is atomic: the symlink only moves on success, so a failed switch leaves the
old release live. Set `rollback = true` in `[switch]` to auto-revert on switch failure.
