# Installation

Install fmd using your preferred Python package manager.

## Using uv (Recommended)

[uv](https://docs.astral.sh/uv/) is a fast Python package installer and resolver.

### Install as a tool

```bash
uv tool install frappe-deployer
```

This installs fmd globally and makes the `fmd` command available.

### Run without installing

```bash
uvx frappe-deployer --help
```

This runs fmd directly from PyPI without permanent installation.

### Install development version

```bash
uv tool install git+https://github.com/rtcamp/fmd@main
```

### Upgrade

```bash
uv tool upgrade frappe-deployer
```

## Using pipx

### Install

```bash
pipx install frappe-deployer
```

### Install development version

```bash
pipx install git+https://github.com/rtcamp/fmd@main
```

### Upgrade

```bash
pipx upgrade frappe-deployer
```

## From Source

### Clone the repository

```bash
git clone https://github.com/rtcamp/fmd.git
cd fmd
```

### Install in development mode

```bash
pip install -e .
```

This creates an editable installation — changes to the source code take effect immediately.

### Install with uv

```bash
uv pip install -e .
```

## Verify Installation

Check that fmd is installed correctly:

```bash
fmd --version
```

You should see output like:

```
fmd version 0.1.0
```

Check available commands:

```bash
fmd --help
```

## Configuration

### GitHub Token

Set up your GitHub token for private repositories:

```bash
export GITHUB_TOKEN=ghp_your_token_here
```

Add to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.) to persist:

```bash
echo 'export GITHUB_TOKEN=ghp_your_token_here' >> ~/.bashrc
```

Alternatively, add it to your config file (see [Configuration Guide](../guides/configuration.md)).

### Frappe Cloud (optional)

If you plan to sync from Frappe Cloud, set up credentials:

```bash
export FC_API_KEY=your_api_key
export FC_API_SECRET=your_api_secret
```

Or add to your config file:

```toml
[fc]
api_key = "your_api_key"
api_secret = "your_api_secret"
site_name = "yoursite.frappe.cloud"
team_name = "your-team"
```

## Troubleshooting

### Command not found

If `fmd` command is not found after installation:

**uv/pipx**: Ensure the tool installation directory is in your PATH:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**From source**: Ensure you're in the correct virtual environment or the installation directory is in your PATH.

### Permission denied

If you get permission errors during installation:

**Never use sudo with pip**. Use `uv tool` or `pipx` instead, which install in user space.

If you must use pip directly:

```bash
pip install --user frappe-deployer
```

### Network issues behind proxy

Configure proxy settings:

```bash
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
uv tool install frappe-deployer
```

## Next Steps

Now that fmd is installed, proceed to the [Quick Start](quick-start.md) guide to deploy your first site.
