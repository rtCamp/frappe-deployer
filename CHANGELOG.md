# Changelog

All notable changes to fmd (Frappe Manager Deployer) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Bug Fixes

- Correct deployment dir handling in DeploymentManager

- Display error log content on CLI in error scenarios

- Host mode deployments

- Instead of symlinking the site, symlink the all subdirs of site

- Improve error handling and validation in host config and main module

- Don't default for mode

- Correct encryption key copying in deployment manager

- Handle app repo keys in a case-insensitive manner

- Restore commented out deployment functions

- Correct Docker command for app reinstall in remote worker

- Relase dir remote sync logic

- Handle DockerException for UV installation check

- Handle uv check when not previously installed

- Remove redundant encryption_key update line

- Update default flag for remove_remote to True

- Add backup condition in DeploymentManager

- Handle live_lines edge cases for CI and TTY

- Handle missing emoji_code in printer method

- Correct directory path strings in create_required_directories

- Add SSH options to disable host key checking in ssh_run

- Ensure UV binary is executable

- Correct ownership command in action.yml

- Correct ownership command in action script

- Correct ownership command in action.yml

- Add group to Docker user configuration

- Correct ownership of bench directory in build process

- Adjust ownership parameter in chown_dir method

- Ensure target_path permissions are updated

- Correct deploy script path for GitHub Actions

- Correct deploy script path in action.yml

- Correct dictionary creation syntax in build_image

- Append --push flag to build command

- Pass GITHUB_TOKEN to build-image command

- Update cleanup logic in action.yml

- Enable production flag in build command

- Update Python version and Frappe version reference

- Fmx path

- Python_version utilization from config

- Remove installation of frappe with bench

- Add back frappe

- Bench installation in env

- Handle empty output from list-apps command

- Stabilize deployment and fix app listing

- Handle DockerException in get_site_installed_apps

- Fix NameError in get_site_installed_apps

- Clear cache on new bench during deploy

- Handle errors during bench CLI setup

- Remove incomplete venv during setup

- Default to exec mode for release creation

- Refine rollback on failed release switch

- Fix symlink creation with existing directories

- Fix unsafe command joining in Docker runner

- Separate fnm install and default commands

- Remove vars/secrets expressions from action.yml description field

- Pass shell args to python3 heredoc in merge_toml

- Replace --config-overrides with single merged --config file

- Write TOML strings to temp files before merging

- Use toml.dumps() for TOML output instead of manual formatter

- Chown release dir to frappe before running container

- Chmod 777 release dir before each Docker run instead of chown

- Use umask 000 in container so host runner can read all created files

- Chmod 777 release dirs on creation so container frappe user can write into them

- Pass USERID/USERGROUP to container so frappe uid matches host runner uid

- Use exec-entrypoint.sh with USERID/USERGROUP so container runs as host runner uid

- Exec-entrypoint.sh is at /exec-entrypoint.sh not /scripts/

- Chmod 777 seeded .fnm/.uv dirs so container runner uid can write into them

- Override HOME to bind-mounted bench dir via wrapper entrypoint

- Replace exec-entrypoint.sh wrapper with standalone entrypoint

- Run container as host runner uid directly, HOME=bind-mount

- Mount bench at /bench not /workspace/frappe-bench

- Chmod /workspace to 755 before gosu drop to runner uid

- Drop /bin/bash prefix from command — entrypoint already is /bin/bash

- **docker**: Run container as root to bypass seccomp/uid permission issues in CI

- **docker**: Usermod frappe to host uid then gosu frappe — bench refuses root

- **docker**: Add chown bench directory to frappe after uid/gid remap

- **ship**: Detect branch from GITHUB_REF in detached HEAD state

- **action**: Pass FMD_ACTION_REF to resolve correct fmd source remotely

- **config**: Skip repo validation in configure/switch commands

- **config**: Use contextvar to skip repo validation before Pydantic construction

- **action**: Only override TOML config when input explicitly provided

- **docs**: Use 'backups' (plural) consistently in env var examples

- **deploy**: Toml_get should check root level before [ship] section

- **deploy**: Use correct fmd executable name in pull command

- **pull**: Use FMD_ACTION_PATH env var for remote fmd installation

- **pull**: Remove [pull] section from config before syncing to remote

- **symlinks**: Create parent directories when creating deployment-data dir

- **pull**: Force host mode for remote deployment to avoid Docker

- **pull**: Create ReleaseConfig if missing before setting host mode

- **runners**: Respect release.mode=host in build_runners()

- **config**: Use host filesystem paths when mode=host

- **pull**: Use environment variables for bare host paths instead of fake mode

- **pull**: Actually use env_vars in SSH command

- **config**: Check FMD_BARE_HOST at runtime in workspace_root property

- **pull**: Export env vars in SSH command for child process inheritance

- **pull**: Export each env var separately with && chain

- **config**: Remove /workspace subdir from bench_path on bare host

- **config**: Correct understanding of directory structure

- **pull**: Export each env var separately with && chain

- **pull**: Use env command to set environment variables


### Build System

- Update frappe-manager dependency

- Pass host and app env vars to build

- Standardize on uv for Python package management

- Migrate from Poetry to UV and Hatch

- Dynamically configure remote host for deploy


### CI/CD

- Add GitHub Actions for testing and image building

- Add tmate session setup to workflow

- Set CI environment variable for deploy script

- Add tmate session for debugging in GitHub Actions

- Update action to include additional inputs

- Configure Git for authenticated cloning


### Dependencies

- **deps**: Bump gitpython from 3.1.44 to 3.1.46


### Documentation

- Add detailed documentation for advanced features

- Add initial project documentation

- Improve documentation content and structure

- Update README with new features and enhancements

- Update Python version info in README

- Migrate README to Org-mode and update details

- Simplify deploy modes to two

- Document ship mode flow and repo validation fix

- Automate CLI command reference generation


### Features

- Implement new configuration and deployment setup

- Add deployment key configuration script to automate GitHub deploy key configuration

- Add utility functions and refactor config handling

- Add config string support and rollback feature

- Create backup dir and Add support for restoring from .gz database files in bench_restore function

- Symlink data sites dirs 1st level to new release

- Add script to configure and manage GitHub deploy keys for multiple repositories

- Add functionality to save config as TOML file

- Add search and replace functionality in database

- Add version output for CLI tool

- Add remote worker management

- Start scheduler and redis-cache with worker services

- Add verbose and force options to deployment commands

- Add cleanup command for deployment backups and cache

- Add cleanup options and interactive prompts

- Add pre-build and post-build command support for FM mode

- Refactor pre-build and post-build command execution in FM mode

- Enhance script environment setup with app-specific variables and custom working directory support

- Add fmd alias for frappe-deployer command

- Add remote-name parameter for app cloning

- Add support for subdirectories in app cloning

- Add overwrite and backup options to app cloning

- Add Frappe Cloud integration with APIs

- Remove specific config keys from fc_site_config

- Add CLI commands for Frappe deployment

- Add latest commit message to app info

- Add symlink support for subdirectory apps

- Add support for remote worker configuration

- Add remote worker sync toggle option

- Add support for syncing dotfiles directories

- Add build system for managing Frappe deploys

- Add support for building Frappe and Nginx images

- Add image type parameter for build command

- Add user isolation for frappe-deployer

- Add chown_dir method to manage directory ownership

- Add support for custom image build labels

- Add support for Docker image pushing

- Add configure_apps flag for deployment control

- Add pnpm activation in Dockerfile

- Add support for additional APT packages

- Handle venv paths for FM container mode

- Enhance worker draining and migration controls

- Add per-app environment variables

- Allow commands to run without config file

- Enhance release creation and runtime setup

- Introduce comprehensive deployment config

- Enhance release listing with detailed info

- Add exec mode availability fallback

- Add configurable release runner mode

- Add timestamped releases and auto-env detection

- Introduce distinct bench name configuration

- Implement Frappe Cloud app and dependency sync

- Rework deploy modes, rename to fmd, update docs

- Improve command output, logging, and CI support

- Add 'ship' deployment strategy

- Enhance CLI with rich examples and version info

- Enable auto-help for Typer commands and apps

- Support common site config in release process

- Enhance configuration with TOML overrides

- **config**: Add environment variable substitution in TOML files

- **deploy**: Read sitename from TOML config when input not provided

- **deploy**: Use config override pattern for pull method switch options

- **pull**: Make pull deployment location-aware via [pull] config section

- Improve config merge and remote home resolve


### Miscellaneous

- Update dependencies and imports across files DONE TILL: db_from_file or fm bench name

- Update dependencies and add ruff to Pipfile, backup, restore from db, validations

- Update version and dependency branch in pyproject.toml

- Update long msg

- Remove deprecated script for configuring GitHub deploy keys

- Bump project version to 0.3.2

- Bump version to 0.5.0 in pyproject.toml

- Bump version to 0.7.0 in pyproject.toml

- Bump version to 0.7.4 in pyproject.toml

- Bump version to 0.7.5 in init and pyproject.

- Bump package version to 0.7.7

- Bump version to 0.7.8 in pyproject.toml

- Update version to 0.7.9 in project files

- Update frappe-manager package branch

- Bump version to 0.8.0

- Bump version to 0.8.1

- Bump version from 0.8.0 to 0.8.1

- Update package dependencies

- Bump version to 0.8.2

- Update version to 0.8.2

- Update version to 0.9.0

- Bump version to 0.10.0

- Update frappe-manager branch in pyproject.toml

- Bump version to 0.11.0

- Remove Pipenv dependency files

- Bump version to 0.11.4

- Bump version to 0.12.0

- Bump version to 0.12.1

- Update frappe-manager dependency branch to develop

- **deps-dev**: Bump urllib3 from 2.3.0 to 2.6.3

- Add dependabot configuration

- Add test configuration file in GitHub

- Make deploy.sh executable

- Comment out tmate session setup

- Create workspace directory in action script

- Add checkout step to GitHub Actions

- Add environment variables to action.yml

- Bump version to 0.13.0

- Bump version to 0.13.1

- Add debug print and exit

- Update Python dependencies

- Remove Devbox environment configuration

- Remove supervisor config from release creation

- Set default maintenance mode phases to migrate

- Delete unused progress mock and test config

- Configure Git SSH command

- Remove direnv configuration file

- Refactor internals, update CI, and improve tests

- Use fmd command in deploy script

- Remove debug logging added during troubleshooting

- Remove site/ build artifacts from git tracking


### Other

- Initial commit

- V0.3.0

- Update pyproject.toml

- Deployment Manager: Version lock bench

- Revert "chore: Bump version to 0.8.1"

This reverts commit 2079c8e25d08b790192e5f1d0ec3ded259fff9cf.

- Revert "Deployment Manager: Version lock bench"

This reverts commit 9ef4626fcda1fdbd60db4257126efa2a23518d53.

- Merge pull request #1 from Xieyt/fm_build_option

feat: Add pre-build and post-build command support for FM mode

- Add MIT License to the project

- Merge pull request #10 from rtCamp/feat/build-images

feat: Add command to create standalone bench directories

- Merge pull request #11 from rtCamp/feat/build-images

refactor: Update class access to use instance-based config

- Merge pull request #19 from rtCamp/chore/add-dependabot-xyz

Enable Dependabot Ecosystems

- Merge pull request #20 from rtCamp/dependabot/pip/gitpython-3.1.46

chore(deps): bump gitpython from 3.1.44 to 3.1.46

- Update scripts/deploy.sh

Co-authored-by: Copilot <175728472+Copilot@users.noreply.github.com>

- Update scripts/helpers.sh

Co-authored-by: Copilot <175728472+Copilot@users.noreply.github.com>

- Update scripts/helpers.sh

Co-authored-by: Copilot <175728472+Copilot@users.noreply.github.com>

- Update frappe_deployer/config/config.py

Co-authored-by: Copilot <175728472+Copilot@users.noreply.github.com>

- Update scripts/deploy.sh

Co-authored-by: Copilot <175728472+Copilot@users.noreply.github.com>

- Update scripts/helpers.sh

Co-authored-by: Copilot <175728472+Copilot@users.noreply.github.com>

- Merge pull request #15 from rtCamp/fix/remote-workers

Misc Fixes and Fix remote workers configuration

- Merge branch 'main' into dependabot/pip/urllib3-2.6.3

- Merge pull request #17 from rtCamp/dependabot/pip/urllib3-2.6.3

chore(deps-dev): Bump urllib3 from 2.3.0 to 2.6.3

- Merge pull request #23 from rtCamp/fix/venv

Fix: frappe-deployer-venv creation

- Add uvx support, auto remote_path, fmd_source config

- Fix tilde expansion, add skip-rsync, fix bench_path for ship mode

- Skip-rsync only skips release sync, not config sync

- Fix configure --no-backups flag not being passed to manager

- Use absolute paths for volume mounts

- Fix configure check to use ssh.is_symlink only (not local Path)

- Add [configure] section with backups field, separate from [switch].backups

- Add rollback field to [configure] section (default true)

- Add [configure] section to example-config.toml

- Fix mkdir to create parent workspace directory automatically

- Fix remote switch to pass bench_name argument

- Remove redundant bench_name from remote switch command (read from config)

- Ship needs to pass bench_name to remote switch (Typer positional arg requirement)

- Add automatic live logging to all FMD commands

- Use switch migrate settings instead of hardcoded False

- Add multi-arch platform detection and configuration

- Add platform parameter to DockerRunner for multi-arch support
- Detect remote architecture in ship mode via SSH (uname -m)
- Map arch to Docker platform (x86_64->linux/amd64, aarch64->linux/arm64)
- Add [release].platform config option for explicit platform override
- Pass DOCKER_DEFAULT_PLATFORM env var to containers
- Auto-detect platform in ship mode, use local arch in image mode
- Document platform field in example-config.toml

- Add logging to _resolve_fmd_source to diagnose detached HEAD issue

- **pull**: Add comprehensive diagnostics for workspace path issue

- Add logging to workspace_root to verify env vars

- Add logging to workspace_root to verify env vars

- Write to stderr for env var checks

- Add benches_root config option for bare host deployments

- Add benches_root field to PullConfig to specify root directory for benches
- Update pull command to use benches_root from config instead of hardcoded path
- Makes bare host deployments configurable via [pull] section
- Env vars only set if benches_root is configured, maintaining backward compatibility

- Keep pull config in remote config file

- Remove line that strips pull section from remote config
- Remote fmd process needs pull.benches_root to set env vars correctly
- This fixes workspace_root calculation in bare host deployments

- Strip pull section from remote config to prevent recursion

- Add debug logging for benches_root and env vars

- Use export instead of env for environment variables

- Env vars must be in Python process environment before module import
- CLI_BENCHES_DIRECTORY is set at module import time (line 11-19 config.py)
- Using 'env VAR=value' sets vars in command environment but too late for import
- Using 'export VAR=value;' sets vars in shell, inherited by Python process

- Use on_remote flag instead of stripping pull config

- Add on_remote boolean field to PullConfig (default False)
- Set on_remote=True in remote config to prevent recursion
- Check 'config.pull.on_remote' instead of stripping config
- workspace_root now checks pull.benches_root directly (no env vars)
- Simpler, more explicit, preserves all config values

- Add debug logging to workspace_root

- Use print for debug output instead of stderr

- Add failsafe error for on_remote without benches_root

- Fix workspace_root for bare host by stripping ship config

- Fix bench_path to include workspace subdirectory

- Pass github_token via config instead of CLI flag

- Fix GitHub token auth format for modern PATs

- Don't mask secrets when syncing remote config

- Add SSH keepalive to prevent timeout on long builds


### Refactoring

- Improve config and deployment management

- Improve deployment logic and exception handling

- Improve import ordering and error handling

- Add decorator to enrich logging with emojis

- Move patched function to config module

- Update method call to printer in deployment_manager

- Improve deployment manager code and fix type hints

- Improve symlink logging and error handling in deployment manager

- Simplify comments and remove commented-out code in deployment_manager.py

- Streamline symlink and directory management

- Update restart command for FM mode

- Simplify DeploymentManager configuration logic

- Add rich_help_panel to typer options

- Improve config handling and file download logic

- Revise app cloning and config handling

- Update JSON merging and clean up spacing

- Restructure CLI commands into separate modules

- Update CLI structure and imports

- Simplify and clean up configuration commands

- Simplify and enhance deployment commands

- Update `sync` and `stop_all_compose_services`

- Replace config instance with cls reference

- Update class access to use instance-based config

- Reorder flags and slice command list

- Update ENTRYPOINT and clean up Dockerfile

- Simplify build process and update configurations

- Remove commented-out image existence checks

- Simplify image build process and class structure

- Remove unused sitename check in deploy script

- Reorganize tmate setup and mkdir logic

- Simplify setup and installation steps

- Consolidate uv installation into frappe-deployer step

- Update action.yml for improved setup flow

- Simplify and enhance user creation logic

- Improve script execution workflow

- Simplify bash command structure in action.yml

- Simplify workspace handling and permissions

- Simplify workspace handling and script execution

- Standardize string quotes and update comments

- Simplify action.yml user setup and permissions

- Reorder tmate setup step in action

- Simplify user and group retrieval in build logic

- Simplify build and deploy logic

- Update output handling for build commands

- Simplify typing imports in config.py

- Simplify tag computation in BuildFrappeConfig

- Simplify app build logic in deployment manager

- Rename github_token to FRAPPE_DEPLOYER_GITHUB_TOKEN

- Use temporary directory for script execution

- Simplify and clarify deployment manager code

- Simplify and clean deployment manager logic

- Update printer methods in deployment manager

- Improve virtual environment creation logic

- Improve sensitive value masking logic

- Improve remote action deployment setup

- Restructure project to FMD package

- Refactor configure method for better rollback

- Restructure deployment configuration

- Rename deploy_dir_path to workspace_root

- Refactor release command build directory

- Refactor deploy command options and runner handling

- Consolidate restart_services logic

- Refactor host run and service restart

- Refactor error message printing

- Refactor deploy config to use TOML overrides

- **deploy**: Extract common functions and fix inconsistencies


### Styling

- Rename readme-usage.org to README.org

- Remove unnecessary blank line


<!-- generated by git-cliff -->
