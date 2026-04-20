# Building the Documentation

This guide explains how to build and preview the fmd documentation site locally.

## Prerequisites

Install development dependencies:

```bash
cd /path/to/fmd
uv sync --group dev
```

This installs:
- **zensical** - MkDocs Material wrapper
- **mike** - Documentation versioning
- **pytest** and testing tools

Alternatively, install globally:

```bash
uv tool install zensical
uv tool install mike
```

Or use [just](https://github.com/casey/just) commands (recommended):

```bash
# Install just
brew install just  # macOS
cargo install just  # Cross-platform via Rust

# View available commands
just
```

## Build the Docs

### Development Server (Live Reload)

Start a live-reloading development server for local editing:

```bash
just docs
# or
uv run zensical serve -a 127.0.0.1:8000
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

Changes to markdown files auto-reload. **Note**: This mode doesn't show the version selector.

### Preview Versioned Docs Locally

To preview with the version selector (requires deploying first):

```bash
# First deploy a version
just docs-deploy dev

# Then serve versioned docs
just docs-versioned
# or
uv run mike serve -F zensical.toml -a 127.0.0.1:8000
```

### Build Static Site

Build the static HTML site without deploying:

```bash
just docs-build
# or
uv run zensical build
```

Output goes to `site/` directory.

## Versioned Documentation (mike)

fmd uses [mike](https://github.com/jimporter/mike) to maintain multiple documentation versions.

### Deploy Development Version

Deploy current code as `dev` version:

```bash
just docs-deploy dev
# or
version=$(uv run python -c "from fmd.__about__ import __version__; print(__version__)")
uv run mike deploy dev --title "$version" -F zensical.toml
```

### Deploy Release Version

Deploy and mark as latest (for releases):

```bash
just docs-release
# or manually:
uv run mike deploy --push --update-aliases v1.0 latest --title "1.0.0" -F zensical.toml
```

This creates:
- Version alias: `v1.0` (major.minor)
- Marks it as `latest`
- Pushes to `gh-pages` branch

### Set Default Version

Set which version users see by default:

```bash
just docs-default latest
# or
uv run mike set-default --push latest -F zensical.toml
```

### List Versions

```bash
just docs-list
# or
uv run mike list -F zensical.toml
```

### Delete a Version

```bash
just docs-delete v0.9
# or
uv run mike delete v0.9 -F zensical.toml
```

## Documentation Structure

```
docs/
├── index.md                    # Home page
├── getting-started/            # Installation and quick start
│   ├── index.md
│   ├── requirements.md
│   ├── installation.md
│   └── quick-start.md
├── guides/                     # Feature guides
│   ├── index.md
│   ├── deploy-modes.md
│   ├── configuration.md
│   ├── github-actions.md
│   └── ...
├── commands/                   # Command reference
│   ├── index.md
│   ├── deploy.md
│   ├── release.md
│   └── ...
├── reference/                  # Technical reference
│   ├── index.md
│   ├── concepts.md
│   ├── architecture.md
│   ├── directory-structure.md
│   └── troubleshooting.md
├── faq.md
├── changelog.md
└── assets/
    └── stylesheets/
        └── extra.css
```

## Writing Documentation

### Style Guide

- Use **bold** for UI elements, commands, and emphasis
- Use `code` for: commands, filenames, config keys, code snippets
- Use admonitions for important notes:
  - `!!! tip` for helpful hints
  - `!!! warning` for cautions
  - `!!! info` for general information
  - `!!! example` for examples

### Code Blocks

Use fenced code blocks with language:

````markdown
```bash
fmd deploy pull --config site.toml
```

```toml
site_name = "mysite.localhost"
```
````

### Admonitions

```markdown
!!! tip "Optional Title"
    This is a helpful tip.

!!! warning
    This is a warning.
```

### Tabbed Content

```markdown
=== "Tab 1"
    Content for tab 1

=== "Tab 2"
    Content for tab 2
```

### Grid Cards

```markdown
<div class="grid cards" markdown>

-   :material-icon:{ .lg .middle } &nbsp; **[Title](link.md)**

    ---

    Description text here.

</div>
```

## Configuration

Documentation is configured in `zensical.toml`:

- **Site metadata**: name, description, URL
- **Navigation**: menu structure
- **Theme**: colors, features, icons
- **Social links**: GitHub, PyPI

See the [Zensical documentation](https://github.com/zkv-tools/zensical) for advanced configuration.

## Deployment Workflow

### Automatic (via GitHub Actions)

Documentation is automatically deployed when:

1. Push to `main` branch
2. GitHub Actions builds docs with mike
3. Deploys to `gh-pages` branch

See `.github/workflows/docs.yml` for the workflow.

### Manual Deployment

For immediate deployment:

```bash
just docs-release
```

This:
1. Extracts version from `fmd/__about__.py`
2. Creates version slug (e.g., `v1.0` from `1.0.0`)
3. Deploys with aliases: `v1.0` and `latest`
4. Pushes to `gh-pages` branch

### Version Strategy

- **Development**: Deploy as `dev` (doesn't affect version history)
- **Releases**: Deploy as `vX.Y` + `latest` (e.g., `v1.0`, `v1.1`)
- **Default**: Set `latest` as default redirect

Example workflow:

```bash
# During development
just docs-deploy dev

# On release v1.0.0
just docs-release  # Creates v1.0 + latest

# On release v1.1.0
just docs-release  # Creates v1.1 + latest (v1.0 still accessible)
```

## Local Preview

To preview the exact site that will be deployed:

```bash
zensical build
cd site
python -m http.server 8000
```

Open [http://localhost:8000](http://localhost:8000).
