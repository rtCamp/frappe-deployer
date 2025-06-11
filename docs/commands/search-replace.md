# search-replace

Search and replace text across all database text fields.

## Synopsis

```bash
frappe-deployer search-replace SITE_NAME SEARCH REPLACE [OPTIONS]
```

## Description

Performs search and replace operations across all varchar and text columns in the site's database. Useful for:

- Domain name changes
- URL updates after site migration
- Configuration value updates
- Data sanitization

## Arguments

- `SITE_NAME` - Name of the site
- `SEARCH` - Text to search for
- `REPLACE` - Text to replace with

## Options

- `--dry-run` - Show what would be changed without making changes
- `--verbose`, `-v` - Show detailed output including before/after values

## Examples

### Dry Run (Recommended First)
```bash
frappe-deployer search-replace my-site \
  "old-domain.com" \
  "new-domain.com" \
  --dry-run
```

### Actual Replacement
```bash
frappe-deployer search-replace my-site \
  "old-domain.com" \
  "new-domain.com"
```

### Verbose Output
```bash
frappe-deployer search-replace my-site \
  "http://localhost" \
  "https://production.com" \
  --verbose
```

## How It Works

1. **Database Scan**: Examines all tables in the site's database
2. **Column Filter**: Targets only `varchar` and `text` data types
3. **Pattern Match**: Uses SQL `LIKE` with wildcards for searching
4. **Bulk Update**: Performs `REPLACE()` operations on matching columns
5. **Progress Report**: Shows matches found and replacements made

## Sample Output

```
Search/Replace Summary:
'old-domain.com' -> 'new-domain.com'
Total replacements: 42

Found 12 matches in tabUser.email
Found 8 matches in tabWebsite Settings.domain
Found 22 matches in tabCommunication.content
```

## Safety Features

- **Dry run mode**: Always test first with `--dry-run`
- **Identical check**: Skips operation if search equals replace
- **Transaction safety**: Database changes are committed atomically
- **Backup recommended**: Take backup before running

## Limitations

- Only searches `varchar` and `text` columns
- Uses simple string replacement (not regex)
- Case-sensitive matching
- FM mode only (host mode not implemented)

## Common Use Cases

### Domain Migration
```bash
# After site migration
frappe-deployer search-replace production-site \
  "staging.company.com" \
  "company.com" \
  --dry-run
```

### Protocol Updates
```bash
# HTTP to HTTPS migration
frappe-deployer search-replace my-site \
  "http://" \
  "https://" \
  --dry-run
```

### Development to Production
```bash
# Update development URLs
frappe-deployer search-replace prod-site \
  "localhost:8000" \
  "production.company.com"
```

## Best Practices

1. **Always dry run first**: Verify changes before applying
2. **Take backups**: Use `--backups` flag in deployment
3. **Test critical flows**: Verify application functionality after changes
4. **Document changes**: Keep record of what was replaced
5. **Staged approach**: Make incremental changes for complex replacements

## Troubleshooting

### No Matches Found
```bash
# Check if search string exists
frappe-deployer search-replace my-site "search-term" "search-term" --dry-run
```

### Permission Errors
- Ensure database connection is working
- Verify site exists and is accessible
- Check that FM containers are running

### Performance Issues
- Large databases may take time to process
- Use `--verbose` to monitor progress
- Consider database indexing for frequently searched columns

## See Also

- [pull](pull.md) - Deployment with search-replace
- [Configuration Guide](../configuration.md) - Setting up search-replace in deployments
