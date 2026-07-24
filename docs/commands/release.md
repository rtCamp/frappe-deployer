## `fmd release`

Release commands.

**Usage**:

```console
$ fmd release [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `configure`: One-time setup: converts a plain bench into a versioned release structure.
* `create`: Create a new release: clone apps, build assets, no live bench changes.
* `switch`: Switch live bench symlink to a previously-created release.
* `list`: List all releases, marking the currently active one.
* `shell`: Open an interactive shell inside the build container for a release.
* `info`: Show release info by inspecting each app's git repository.


### `fmd release configure`

One-time setup: converts a plain bench into a versioned release structure.

**Usage**:

```console
$ fmd release configure
```


## Examples

### Configure from config file

Reads bench name and apps from the TOML config and runs one-time release structure setup.

```bash
fmd release configure --config {config_path}
```

### Configure from bench name

Converts a plain bench into a versioned release structure using bench name to locate it.

```bash
fmd release configure mysite
```


### `fmd release create`

Create a new release: clone apps, build assets, no live bench changes.

**Usage**:

```console
$ fmd release create
```


## Examples

### Create with explicit apps

Overrides the apps list from config with the specified repos and refs.

```bash
fmd release create mysite --app frappe/frappe:version-15 --app frappe/erpnext:version-15
```

### Create in image mode with build dir

Builds the release as a standalone directory outside the bench. Activates image mode automatically.

```bash
fmd release create {bench_name} --build-dir {build_dir}
```

### Create from config file

Clones apps, builds assets, and writes a new release directory. No live bench changes.

```bash
fmd release create --config {config_path}
```


### `fmd release switch`

Switch live bench symlink to a previously-created release.

**Usage**:

```console
$ fmd release switch
```


## Examples

### Switch with maintenance mode

Enables maintenance mode during the switch to prevent user-facing errors while the symlink is updated.

```bash
fmd release switch {bench_name} {release_name} --maintenance-mode
```

### Switch with migrate

Runs bench migrate after switching the symlink to apply any pending schema changes.

```bash
fmd release switch {bench_name} {release_name} --migrate
```

### Switch to a release

Updates the live bench symlink to point at the specified release directory.

```bash
fmd release switch {bench_name} {release_name}
```


### `fmd release list`

List all releases, marking the currently active one.

**Usage**:

```console
$ fmd release list
```


## Examples

### List from config file

Reads bench name from config and lists all releases with metadata.

```bash
fmd release list --config {config_path}
```

### List releases by bench name

Lists all releases in the bench workspace, marking the currently active one.

```bash
fmd release list mysite
```


### `fmd release shell`

Open an interactive shell inside the build container for a release.

**Usage**:

```console
$ fmd release shell
```


## Examples

### Shell into latest release from config

Finds the latest release and opens an interactive shell in the build container.

```bash
fmd release shell --config {config_path}
```

### Shell into a specific release

Opens an interactive shell for a specific release directory.

```bash
fmd release shell --config {config_path} {release_name}
```


### `fmd release info`

Show release info by inspecting each app's git repository.

**Usage**:

```console
$ fmd release info
```


## Examples

### Info from config file

Reads bench path from config and shows git info for all apps.

```bash
fmd release info --config {config_path}
```

### Info by bench name

Inspects each app's git repository in the bench and prints commit, branch, and tag info.

```bash
fmd release info mysite
```
