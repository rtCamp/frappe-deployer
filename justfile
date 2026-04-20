# fmd - Justfile for development tasks
# Usage: just <command>

# Default recipe - show available commands
default:
    @just --list

# ── Development ───────────────────────────────────────────────────────────────

# Run tests
test:
    pytest tests/ -v

# Run tests with coverage
test-cov:
    pytest tests/ --cov=fmd --cov-report=html
    @echo "\nCoverage report: htmlcov/index.html"

# Run specific test file
test-file FILE:
    pytest {{FILE}} -v

# ── Documentation ─────────────────────────────────────────────────────────────

# Serve docs locally for development (live reload, no version selector)
docs port="8000":
    uv run zensical serve -a 127.0.0.1:{{port}}

# Serve VERSIONED docs locally via mike (shows version selector, requires deploy first)
docs-versioned port="8000":
    uv run mike serve -F zensical.toml -a 127.0.0.1:{{port}}

# Build docs without deploying
docs-build:
    uv run zensical build

# ── Docs versioning (via mike) ────────────────────────────────────────────────

# Deploy current docs as a named version (e.g. just docs-deploy dev)
docs-deploy alias="dev":
    #!/usr/bin/env bash
    version=$(uv run python -c "from fmd.__about__ import __version__; print(__version__)")
    uv run mike deploy {{alias}} --title "$version" -F zensical.toml

# Deploy and mark as latest (for release tags)
docs-release:
    #!/usr/bin/env bash
    version=$(uv run python -c "from fmd.__about__ import __version__; print(__version__)")
    slug=$(uv run python -c "
    import re
    from fmd.__about__ import __version__
    m = re.match(r'^(\d+\.\d+)', __version__)
    print('v' + m.group(1) if m else __version__)
    ")
    uv run mike deploy --push --update-aliases "$slug" latest --title "$version" -F zensical.toml

# Set the default version redirect (run once after first deploy)
docs-default version="latest":
    uv run mike set-default --push {{version}} -F zensical.toml

# List all deployed doc versions
docs-list:
    uv run mike list -F zensical.toml

# Delete a doc version
docs-delete version:
    uv run mike delete {{version}} -F zensical.toml

# ── Code quality ──────────────────────────────────────────────────────────────

# Format code with ruff
fmt:
    ruff format .

# Lint code with ruff
lint:
    ruff check .

# Fix linting issues
lint-fix:
    ruff check --fix .

# ── Build ─────────────────────────────────────────────────────────────────────

# Build package
build:
    uv build

# Clean build artifacts
clean:
    rm -rf dist/ build/ *.egg-info
    find . -type d -name __pycache__ -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete
