## `fmd cleanup`

Cleanup deployment backups and releases.

**Usage**:

```console
$ fmd cleanup
```


## Examples

### Cleanup and auto-approve

Runs cleanup without prompting for confirmation. Useful in CI or scripts.

```bash
fmd cleanup --config {config_path} --yes
```

### Keep last 3 releases

Deletes all but the 3 most recent releases in the bench workspace.

```bash
fmd cleanup mysite --release-retain-limit 3
```
