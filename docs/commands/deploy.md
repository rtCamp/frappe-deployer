## `fmd deploy`

Deploy commands.

**Usage**:

```console
$ fmd deploy [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `pull`: Full deploy: configure (if needed) → create release → switch.
* `ship`: Ship deploy: create release locally → rsync to remote → switch on remote.


### `fmd deploy pull`

Full deploy: configure (if needed) → create release → switch.

**Usage**:

```console
$ fmd deploy pull
```


## Examples

### Deploy with Frappe Cloud integration

Pulls FC app list and DB backup, then deploys. Requires FC API credentials.

```bash
fmd deploy pull {bench_name} --fc-key {fc_key} --fc-secret {fc_secret} --fc-site {fc_site}
```

### Deploy with explicit apps

Overrides config apps list with specified repos and refs.

```bash
fmd deploy pull mysite --app frappe/frappe:version-15 --app frappe/erpnext:version-15
```

### Deploy from config file

Reads bench name and app list from the TOML config file. Full deploy: configure → create → switch.

```bash
fmd deploy pull --config {config_path}
```


### `fmd deploy ship`

Ship deploy: create release locally → rsync to remote → switch on remote.

**Usage**:

```console
$ fmd deploy ship
```


## Examples

### Skip rsync (release already on remote)

Switches to an already-transferred release without rsyncing again. Useful for retrying a failed switch.

```bash
fmd deploy ship --config {config_path} --existing-release {release_name} --skip-rsync
```

### Ship using an existing release

Skips release creation and rsyncs an already-created local release to the remote, then switches.

```bash
fmd deploy ship --config {config_path} --existing-release {release_name}
```

### Ship from config file

Creates a release locally, rsyncs it to the remote server, and switches the live bench. Requires a [ship] section in config.

```bash
fmd deploy ship --config {config_path}
```

