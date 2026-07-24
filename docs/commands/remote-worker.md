## `fmd remote-worker`

Remote-Worker commands.

**Usage**:

```console
$ fmd remote-worker [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `enable`: Enable remote worker: expose DB + Redis ports, create worker site configs.
* `sync`: Sync workspace to remote worker server.


### `fmd remote-worker enable`

Enable remote worker: expose DB + Redis ports, create worker site configs.

**Usage**:

```console
$ fmd remote-worker enable
```


## Examples

### Enable from config file

Reads bench name and remote worker settings from config, exposes DB/Redis ports and writes worker site configs.

```bash
fmd remote-worker enable --config {config_path}
```

### Enable with bench name

Enables remote worker for the specified bench, pointing at the given remote server IP.

```bash
fmd remote-worker enable {bench_name} --rw-server {rw_server}
```


### `fmd remote-worker sync`

Sync workspace to remote worker server.

**Usage**:

```console
$ fmd remote-worker sync
```


## Examples

### Sync from config file

Reads bench name and remote worker settings from config and syncs the workspace to the remote server.

```bash
fmd remote-worker sync --config {config_path}
```

### Sync with bench name

Syncs the workspace for the specified bench to the remote worker server.

```bash
fmd remote-worker sync {bench_name} --rw-server {rw_server}
```

