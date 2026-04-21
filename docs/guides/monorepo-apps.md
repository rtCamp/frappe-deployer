# Monorepo Apps

!!! info "Coming Soon"
    This guide is under development. Check back soon for complete documentation on deploying apps from monorepo subdirectories.

## What you'll learn

This guide will cover:

- **Subdirectory apps** — Deploy apps from monorepo paths
- **Symlink strategy** — How fmd handles subdirectory apps
- **Workspace efficiency** — Benefits of monorepo structure
- **Common patterns** — Multiple apps in one repository
- **Troubleshooting** — Path resolution issues

## Quick preview

Deploy an app from a monorepo subdirectory:

```bash
fmd deploy pull mysite.localhost \
  --app my-org/monorepo:main:apps/my-app
```

Format: `org/repo:ref:subdir_path`

Or in configuration:

```toml
[[apps]]
repo = "my-org/monorepo"
ref = "main"
subdir_path = "apps/my-app"
```

## How it works

(Documentation in progress)

When you specify a `subdir_path`:

1. fmd clones the full repository
2. Creates a symlink from workspace to `apps/my-app` subdirectory
3. Frappe bench sees it as a normal app
4. Updates pull only changed files (efficient)

## Common patterns

(Documentation in progress)

### Multiple apps in one repo

```toml
[[apps]]
repo = "my-org/monorepo"
ref = "main"
subdir_path = "apps/frontend"

[[apps]]
repo = "my-org/monorepo"
ref = "main"
subdir_path = "apps/backend"
```

### Shared libraries
Monorepo with shared code and multiple app directories.

### Versioned apps
Different branches for different app versions.

## Directory structure

(Documentation in progress)

Example monorepo layout:

```
my-org/monorepo/
├── apps/
│   ├── frontend/       ← Deploy this
│   │   ├── frontend/
│   │   ├── setup.py
│   │   └── ...
│   └── backend/        ← Or this
│       ├── backend/
│       ├── setup.py
│       └── ...
├── shared/
│   └── utils/
└── README.md
```

## Next steps

For now, see the [Quick Start Guide](../getting-started/quick-start.md#deploy-a-monorepo-app) for a working example.
