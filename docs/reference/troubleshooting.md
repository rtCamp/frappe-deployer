# Troubleshooting

Common fmd-specific issues and solutions.

## Configuration Issues

### Private Repository Access

**Problem**: Ship mode fails with "repo not accessible" during remote configure
```
Error: repo not accessible: ApexTraderFunding/private-app
RuntimeError: Please ensure all app repos are accessible.
```

**Root Cause**: Ship mode runs configure/switch on remote server where private repos aren't accessible.

**Solution**: This is expected and should work automatically since v0.x (fmx/0 branch). The remote configure step **skips** repository validation because it uses pre-built artifacts from the local build.

**How it works internally**:
1. Local build (CI/local): Validates repos and builds artifacts ✅
2. Rsync to remote: Transfers built artifacts
3. Remote configure: Skips validation (uses contextvars.ContextVar) ✅
4. Remote switch: Activates release

If you still see this error:
- Ensure you're using `rtcamp/frappe-deployer@fmx/0` or later
- Check that `FMD_ACTION_REF` environment variable is set correctly
- Verify remote fmd is installed from correct branch via uvx

**Problem**: Can't clone private repos during local build
```
ERROR: Repository access denied
```

**Solution**: Set GitHub token in config or environment
```bash
# Via config file
github_token = "ghp_xxx"

# Via environment
export GITHUB_TOKEN=ghp_xxx
fmd deploy pull --config site.toml

# Test token
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
```

**Token requires `repo` scope for private repositories.**

### Invalid TOML Syntax
**Problem**: Config validation fails with cryptic errors

**Solution**: Validate TOML syntax
```bash
# Use Python TOML parser
python3 -c "import tomllib; tomllib.load(open('site.toml', 'rb'))"

# Common issues:
# - Missing quotes: repo = frappe/frappe  # ❌ Wrong
#                   repo = "frappe/frappe" # ✅ Correct
# - Unescaped backslashes in paths (Windows)
# - Invalid TOML tables: [[apps] instead of [[apps]]
```

### Frappe Cloud Integration Failures
**Problem**: FC sync fails with auth errors

**Solution**: Verify API credentials and site name
```bash
# Test FC API access
curl -u fc_key:fc_secret \
  https://frappecloud.com/api/method/press.api.bench.apps

# Check team/site names match exactly
```

```toml
[fc]
site_name = "mysite.frappe.cloud"  # Must match FC site name
team_name = "my-team"              # Must match FC team slug
```

**FC integration requires ALL three fields**: `api_key`, `api_secret`, `site_name` (and optionally `team_name`).

## Deployment Issues

### Release Creation Fails
**Problem**: Git clone or dependency install errors

**Solutions**:
1. **Check network and GitHub access**:
   ```bash
   curl -I https://github.com
   git ls-remote https://github.com/frappe/frappe.git
   ```

2. **Verify app ref exists**:
   ```bash
   # For branch/tag
   git ls-remote --heads --tags https://github.com/frappe/frappe.git | grep version-15
   ```

3. **Check system dependencies**:
   ```bash
   # Ubuntu/Debian
   sudo apt install python3-dev build-essential mariadb-client libmariadb-dev

   # macOS
   brew install mariadb-connector-c
   ```

### Symlink App Not Found
**Problem**: Monorepo app deployment fails
```
ERROR: Subdir path 'apps/my-app' not found in repo
```

**Solution**: Verify subdir path and symlink config
```toml
[[apps]]
repo = "my-org/monorepo"
ref = "main"
subdir_path = "apps/my-app"  # Must exist in repo at this ref
symlink = true               # Required for subdir apps
```

**Check repo structure matches**:
```bash
# Clone and verify path exists
git clone https://github.com/my-org/monorepo.git /tmp/test
ls /tmp/test/apps/my-app  # Should show app files
```

### Database Migration Timeout
**Problem**: Migration exceeds timeout during switch

!!! warning "Migration Timeout Data Loss Risk"
    If migrations are interrupted mid-execution due to timeout, your database may be left in an inconsistent state. Always test migrations on a staging environment first, and take backups before production deployments.

**Solution**: Increase migration timeout
```toml
[switch]
migrate_timeout = 600  # 10 minutes (default: 300)
```

**For very large DBs**: Migrate manually before switch, then set `migrate = false`.

### Worker Drain Timeout
**Problem**: Workers don't finish jobs within timeout

**Solution**: Adjust drain timeouts
```toml
[switch]
drain_workers = true
drain_workers_timeout = 900  # 15 min (default: 300)
skip_stale_timeout = 30      # Wait 30s for stale workers
worker_kill_timeout = 30     # Force kill after 30s
```

**For critical background jobs**: Manually verify workers finished before deploying:
```bash
# FM mode
docker exec -it <container> supervisorctl status

# Host mode
supervisorctl status | grep rq
```

## FM Mode Issues

### Frappe Manager Not Found
**Problem**: fmd can't find FM installation
```
ERROR: frappe_manager package not found
```

**Solution**: Install Frappe Manager
```bash
pip install frappe-manager
fm --version
fm list
```

**fmd requires FM for Docker container management.**

### Container Connection Issues
**Problem**: Can't connect to FM site container

**Solutions**:
1. **Verify site running**:
   ```bash
   fm list
   fm logs site.localhost
   ```

2. **Check Docker**:
   ```bash
   docker ps
   sudo systemctl status docker
   ```

3. **Restart site**:
   ```bash
   fm stop site.localhost
   fm start site.localhost
   ```

### Remote Worker Ports Not Exposed
**Problem**: Remote worker can't connect to Redis/MariaDB

!!! warning "Force Flag Restarts Containers"
    The `--force` flag restarts all Frappe Manager containers to apply port exposure changes. This causes **brief downtime**. Without `--force`, only the configuration is updated without restarting.

**Solution**: Enable remote worker mode
```bash
# Exposes ports 3306 (MariaDB) and 6379 (Redis)
fmd remote-worker enable site.localhost --rw-server 192.168.1.100 --force

# Verify docker-compose
cat ~/frappe/sites/site.localhost/docker-compose.yml | grep ports
```

**Without `--force`, only adds config without restarting containers.**

## Host Mode Issues

### Bench Not Found
**Problem**: Can't locate bench directory

**Solution**: Verify `bench_path` or create new bench
```bash
# Check if bench exists
ls -la ~/frappe-bench/apps
cat ~/frappe-bench/apps.txt

# Create new bench (if needed)
bench init --frappe-branch version-15 ~/frappe-bench
```

**In config**: `bench_path` is mutually exclusive with FM mode.

### Python Version Mismatch
**Problem**: Bench requires different Python version

**Solution**: Install correct Python and set explicitly
```toml
[release]
python_version = "3.11"  # Must match system Python
```

```bash
# Ubuntu/Debian
sudo apt install python3.11 python3.11-dev python3.11-venv

# macOS
brew install python@3.11
```

**fmd requires Python 3.10+ (not 3.8 as old docs claimed).**

### UV Installation Fails
**Problem**: UV download or execution errors

**Solution**: fmd auto-downloads UV, but check system compatibility
```bash
# Verify UV installed
ls -la .venv/bin/uv

# Manual install
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**fmd always uses UV for package installs (fallback to pip on UV failure).**

## Rollback and Recovery

### Release Switch Fails Mid-Deployment
**Problem**: Error during `fmd release switch`

**Recovery**:
1. **Symlink still points to old release** (switch is atomic via symlink, only changes on success)
2. **Check current release**:
   ```bash
   fmd release list site.localhost
   readlink ~/frappe/sites/site.localhost/workspace/frappe-bench
   ```
3. **Manual rollback** (if needed):
   ```bash
   fmd release switch site.localhost release_20250409_150000
   ```

**Automatic rollback**: Set `rollback = true` in `[switch]` config for auto-rollback on switch failure.

### Restore from Backup
**Problem**: Deployment corrupted database

!!! danger "Database Restore Overwrites Current Data"
    Restoring from backup **permanently deletes** your current database and replaces it with the backup. This action is irreversible. Always verify you have the correct backup file and take a fresh backup of the current state before restoring.

**Solution**: Manual restore from deployment-backup
```bash
# Find backup
ls -lt ~/frappe/sites/site.localhost/deployment-backup/

# Restore manually
cd ~/frappe/sites/site.localhost/workspace/frappe-bench
bench --site site.localhost restore /path/to/backup.sql.gz
```

**Automatic backups**: Enabled via `backups = true` in `[switch]` config (default: true).

## Performance Issues

### Slow App Cloning
**Problem**: Git clones take forever

**Solutions**:
1. **Check network**:
   ```bash
   speedtest-cli
   ```

2. **Use shallow clone** (future feature, not yet implemented)

3. **Pre-clone locally and use `file://` URL**:
   ```toml
   [[apps]]
   repo = "file:///tmp/frappe-cache"
   ref = "version-15"
   ```

### High Memory During Install
**Problem**: UV/pip consumes excessive memory

**Solutions**:
1. **Increase swap**:
   ```bash
   sudo fallocate -l 2G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

2. **Monitor resources**:
   ```bash
   htop
   docker stats  # For FM mode
   ```

## Debugging

### Enable Verbose Output
```bash
fmd -v deploy pull site.localhost  # Global -v before subcommand
fmd -v release switch site.localhost release_20250410_120000
```

**Verbose mode shows**:
- Git clone commands
- Dependency install output
- Bench command execution
- Migration logs

### Check Release State
```bash
# List all releases
fmd release list site.localhost

# Show current symlink
readlink ~/frappe/sites/site.localhost/workspace/frappe-bench

# Inspect specific release
ls -la ~/frappe/sites/site.localhost/workspace/release_20250410_120000/
cat ~/frappe/sites/site.localhost/workspace/release_20250410_120000/.fmd.toml
```

### Verify Config
```bash
# Show effective config (after overrides)
fmd info site.localhost --config site.toml

# Validate TOML
python3 -c "import tomllib; print(tomllib.load(open('site.toml', 'rb')))"
```

## Common Errors

### `ModuleNotFoundError: No module named 'frappe_manager'`
**Cause**: Frappe Manager not installed

**Fix**: `pip install frappe-manager`

### `ERROR: bench_path and FM mode are mutually exclusive`
**Cause**: Config has both `bench_path` set AND trying to use FM mode

**Fix**: Remove `bench_path` from config for FM mode, or set `bench_path` for host mode (one or the other, not both)

### `ERROR: Site not found in Frappe Manager`
**Cause**: FM site doesn't exist yet

**Fix**: Create site first:
```bash
fm create site.localhost
# Then deploy
fmd deploy pull site.localhost --config site.toml
```

### `ERROR: Python 3.9 not supported`
**Cause**: fmd requires Python 3.10+

**Fix**: Upgrade Python:
```bash
# Ubuntu/Debian
sudo apt install python3.10 python3.10-venv

# macOS
brew install python@3.10
```

### `ERROR: use_fc_apps enabled but no FC credentials`
**Cause**: FC integration enabled without credentials

**Fix**: Add FC config section:
```toml
[release]
use_fc_apps = true

[fc]
api_key = "fc_xxx"
api_secret = "fc_xxx"
site_name = "mysite.frappe.cloud"
```

## Getting Help

### Collect Debug Information
When reporting issues, include:

```bash
# 1. fmd version
fmd --version

# 2. Python version
python3 --version

# 3. OS info
uname -a

# 4. Full command with verbose output
fmd -v deploy pull site.localhost 2>&1 | tee debug.log

# 5. Config file (remove tokens)
cat site.toml | grep -v token | grep -v api_key

# 6. Release state
fmd release list site.localhost
```

### Resources
- **Configuration**: See [example-config.toml](../example-config.toml) for full schema
- **Concepts**: Read [docs/concepts.md](concepts.md) for architecture understanding
- **Commands**: Check [docs/commands.md](commands.md) for detailed command reference
