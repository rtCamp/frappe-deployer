# Troubleshooting Guide

Common issues and solutions when using frappe-deployer.

## Installation Issues

### Python Version Compatibility
**Problem**: frappe-deployer fails to install or run
```
ERROR: Python 3.7 is not supported
```

**Solution**: Upgrade to Python 3.8 or higher
```bash
# Check current version
python3 --version

# Ubuntu/Debian
sudo apt update && sudo apt install python3.10

# macOS with Homebrew
brew install python@3.10
```

### Permission Errors During Installation
**Problem**: `pip install` fails with permission errors

**Solution**: Use virtual environment or user installation
```bash
# Virtual environment (recommended)
python3 -m venv frappe-deployer-env
source frappe-deployer-env/bin/activate
pip install frappe-deployer

# User installation
pip install --user frappe-deployer
```

## Configuration Issues

### GitHub Token Access
**Problem**: Can't access private repositories
```
ERROR: Repository access denied
```

**Solution**: Verify token permissions
```bash
# Test token access
curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/user

# Ensure token has required scopes:
# - repo (for private repositories)
# - public_repo (for public repositories)
```

### Configuration File Not Loading
**Problem**: Settings from TOML file ignored

**Solution**: Check file path and syntax
```bash
# Verify file exists and is readable
ls -la config.toml
cat config.toml

# Validate TOML syntax online or with:
python3 -c "import toml; toml.load('config.toml')"
```

## Deployment Issues

### Directory Permission Errors
**Problem**: Can't create or access deployment directories
```
ERROR: Permission denied: './deployment-data'
```

**Solution**: Fix ownership and permissions
```bash
# Fix ownership
sudo chown -R $USER:$USER ./deployment-data

# Set proper permissions
chmod -R 755 ./deployment-data
```

### Git Clone Failures
**Problem**: Repository cloning fails
```
ERROR: Could not clone repository frappe/frappe
```

**Solutions**:
1. **Check network connectivity**:
   ```bash
   curl -I https://github.com
   ```

2. **Verify repository exists**:
   ```bash
   curl -I https://github.com/frappe/frappe
   ```

3. **Check GitHub token** (for private repos):
   ```bash
   git clone https://YOUR_TOKEN@github.com/owner/repo.git
   ```

### Database Connection Issues
**Problem**: Can't connect to database during migration

**Solution**: Verify database service and credentials
```bash
# For FM mode - check container status
docker ps
fm logs

# For host mode - check database service
sudo systemctl status mariadb
# or
sudo systemctl status mysql
```

## FM Mode Issues

### Docker/Container Problems
**Problem**: FM commands fail or containers won't start

**Solutions**:
1. **Check Docker service**:
   ```bash
   sudo systemctl status docker
   docker ps
   ```

2. **Verify FM installation**:
   ```bash
   fm --version
   fm list
   ```

3. **Check container logs**:
   ```bash
   fm logs SITE_NAME
   ```

### Container Resource Issues
**Problem**: Out of memory or disk space in containers

**Solution**: Check and adjust resource limits
```bash
# Check disk usage
df -h

# Check container resources
docker stats

# Clean up unused containers/images
docker system prune
```

## Host Mode Issues

### Bench Path Issues
**Problem**: Can't find or access bench directory

**Solution**: Verify bench path and permissions
```bash
# Check if bench path exists
ls -la /path/to/bench

# Verify it's a Frappe bench
ls -la /path/to/bench/apps
cat /path/to/bench/apps.txt
```

### Python Environment Issues
**Problem**: Virtual environment or package installation fails

**Solutions**:
1. **Check Python installation**:
   ```bash
   python3 --version
   which python3
   ```

2. **Recreate virtual environment**:
   ```bash
   rm -rf env
   python3 -m venv env
   source env/bin/activate
   ```

3. **Install system dependencies**:
   ```bash
   # Ubuntu/Debian
   sudo apt install python3-dev python3-venv build-essential
   
   # CentOS/RHEL
   sudo yum install python3-devel gcc
   ```

## Network and Connectivity

### Proxy Issues
**Problem**: Can't download packages or clone repositories behind proxy

**Solution**: Configure proxy settings
```bash
# Set proxy environment variables
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=http://proxy.company.com:8080

# Configure git proxy
git config --global http.proxy http://proxy.company.com:8080
```

### DNS Resolution Issues
**Problem**: Can't resolve GitHub or package repository URLs

**Solution**: Check DNS configuration
```bash
# Test DNS resolution
nslookup github.com
dig github.com

# Try alternative DNS servers
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf
```

## Performance Issues

### Slow Downloads
**Problem**: Package installation or git clones are very slow

**Solutions**:
1. **Use UV package manager**:
   ```toml
   uv = true
   ```

2. **Check network bandwidth**:
   ```bash
   speedtest-cli
   ```

3. **Use local mirrors** (for packages):
   ```bash
   pip install -i https://pypi.douban.com/simple/ package_name
   ```

### High Memory Usage
**Problem**: System runs out of memory during deployment

**Solutions**:
1. **Monitor memory usage**:
   ```bash
   free -h
   htop
   ```

2. **Reduce parallel operations** (implementation dependent)

3. **Add swap space**:
   ```bash
   sudo fallocate -l 2G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

## Backup and Restore Issues

### Backup Creation Failures
**Problem**: Can't create backups before deployment

**Solution**: Check disk space and permissions
```bash
# Check available disk space
df -h

# Verify backup directory permissions
ls -la ./deployment-backup/
sudo chown -R $USER:$USER ./deployment-backup/
```

### Restore Failures
**Problem**: Database restore from backup fails

**Solutions**:
1. **Check backup file integrity**:
   ```bash
   gzip -t backup_file.sql.gz
   ```

2. **Verify database connectivity**:
   ```bash
   mysql -u root -p -e "SHOW DATABASES;"
   ```

3. **Check available disk space**:
   ```bash
   df -h /var/lib/mysql
   ```

## Getting Help

### Enable Verbose Mode
Always use `--verbose` flag when troubleshooting:
```bash
frappe-deployer pull my-site-name --config-path config.toml --verbose
```

### Check Logs
Look for detailed error messages in:
- Command output (with `--verbose`)
- System logs (`/var/log/`)
- Container logs (`fm logs` or `docker logs`)

### Collect Debug Information
When reporting issues, include:
1. frappe-deployer version: `frappe-deployer --version`
2. Python version: `python3 --version`
3. Operating system: `uname -a`
4. Complete command used
5. Full error output with `--verbose`
6. Configuration file (remove sensitive tokens)

### Community Support
- **Documentation**: Check other guides in [docs/](.)
- **Examples**: See [examples/](examples/) for working configurations
- **Issues**: Report bugs on GitHub repository

## Prevention Tips

1. **Test in development first**: Always test deployments in a dev environment
2. **Keep backups**: Ensure backup functionality is enabled
3. **Monitor resources**: Check disk space and memory regularly
4. **Version control configs**: Keep configuration files in git
5. **Document customizations**: Note any custom scripts or configurations
6. **Regular updates**: Keep frappe-deployer updated to latest version
