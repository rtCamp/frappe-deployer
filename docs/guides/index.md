# Guides

In-depth walkthroughs for everything fmd can do.

<div class="grid cards" markdown>

-   :lucide-git-branch:{ .lg .middle } &nbsp; **[Deploy Modes](deploy-modes.md)**

    ---

    Understand pull vs ship deployment strategies. Learn when to build on-server vs build locally and rsync.

-   :lucide-settings:{ .lg .middle } &nbsp; **[Configuration](configuration.md)**

    ---

    Complete guide to the TOML configuration file. All options, defaults, and examples explained.

-   :lucide-github:{ .lg .middle } &nbsp; **[GitHub Actions](github-actions.md)**

    ---

    Automate deployments from CI/CD with the rtcamp/frappe-deployer GitHub Action. Pull and ship strategies.

-   :lucide-zap:{ .lg .middle } &nbsp; **[Hooks & Lifecycle](hooks.md)**

    ---

    Customize every phase of the build and deployment process with shell hooks. Build assets, run tests, send notifications.

-   :lucide-cloud:{ .lg .middle } &nbsp; **[Frappe Cloud Sync](frappe-cloud.md)**

    ---

    Import app lists, Python dependencies, and database backups directly from Frappe Cloud. Perfect for migrations.

-   :lucide-shield-alert:{ .lg .middle } &nbsp; **[Maintenance Mode](maintenance-mode.md)**

    ---

    Control when maintenance mode activates. Bypass tokens for developer access during deployments.

-   :lucide-users:{ .lg .middle } &nbsp; **[Remote Workers](remote-workers.md)**

    ---

    Run background workers on separate servers. Sync releases across machines for distributed setups.

-   :lucide-folder-tree:{ .lg .middle } &nbsp; **[Monorepo Apps](monorepo-apps.md)**

    ---

    Deploy apps from subdirectories of monorepos. Symlink for efficient workspace management.

-   :lucide-undo:{ .lg .middle } &nbsp; **[Rollback & Recovery](rollback.md)**

    ---

    Instant rollback to previous releases. Automatic rollback on migration failures. Backup and restore workflows.

</div>
