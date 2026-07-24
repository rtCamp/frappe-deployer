## `fmd search-replace`

Search and replace text across all text fields in the Frappe database.

**Usage**:

```console
$ fmd search-replace
```


## Examples

### Dry-run search-replace

Shows what would be changed without modifying the database.

```bash
fmd search-replace {bench_name} {search} {replace} --dry-run
```

### Search and replace in DB

Replaces all occurrences of the search text across all text fields in the Frappe database.

```bash
fmd search-replace {bench_name} {search} {replace}
```

