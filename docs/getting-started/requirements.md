# Requirements

Before installing fmd, make sure you have the following:

## System Requirements

### Python 3.10+

fmd requires Python 3.10 or later.

Check your Python version:

```bash
python3 --version
```

If you need to install or upgrade Python:

=== "macOS (Homebrew)"

    ```bash
    brew install python@3.11
    ```

=== "Ubuntu/Debian"

    ```bash
    sudo apt update
    sudo apt install python3.11 python3.11-venv python3-pip
    ```

=== "RHEL/CentOS/Rocky"

    ```bash
    sudo dnf install python3.11
    ```

### Docker

Docker is required for building and running Frappe containers.

Check if Docker is installed:

```bash
docker --version
docker compose version
```

If you need to install Docker:

- **Linux**: Follow the [official Docker installation guide](https://docs.docker.com/engine/install/)
- **macOS**: Install [Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/)
- **Windows**: Install [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/)

!!! warning "Docker Compose V2"
    fmd requires Docker Compose V2 (the `docker compose` command, not the legacy `docker-compose`).

### Frappe Manager

fmd works alongside [Frappe Manager](https://github.com/rtcamp/frappe-manager) to manage Frappe benches.

Install Frappe Manager:

```bash
uv tool install --python 3.13 frappe-manager
```

Or with pipx:

```bash
pipx install frappe-manager
```

Verify installation:

```bash
fm --version
```

## Optional Requirements

### GitHub Personal Access Token

Required for:

- Deploying private repositories
- Avoiding GitHub API rate limits

Create a token at [github.com/settings/tokens](https://github.com/settings/tokens) with `repo` scope.

Store it securely:

```bash
export GITHUB_TOKEN=ghp_your_token_here
```

Or add to your config file:

```toml
github_token = "ghp_your_token_here"
```

### SSH Access (for remote deployments)

If you plan to use `fmd deploy ship` or remote workers, you'll need:

- SSH access to your production server
- Passwordless SSH key authentication configured

Test SSH access:

```bash
ssh user@your-server.com
```

### Frappe Cloud Credentials (optional)

If you want to sync from Frappe Cloud, you'll need:

- Frappe Cloud API key and secret
- Team name and site name

Get these from your [Frappe Cloud dashboard](https://frappecloud.com/).

## Disk Space

Each release requires disk space for:

- Apps repository clones
- Python virtual environment
- Node modules
- Built assets

Minimum recommended: **5 GB free space** per site workspace

Actual usage depends on:

- Number of apps installed
- Number of releases retained (default: 7)
- Backup retention policy

## Network Requirements

fmd needs network access to:

- **GitHub**: Clone app repositories
- **PyPI**: Install Python packages
- **npm registry**: Install Node packages
- **Docker Hub/GHCR**: Pull container images

If deploying behind a proxy, configure:

```bash
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
```

## Next Steps

Once you have all requirements installed, proceed to [Installation](installation.md).
