#!/usr/bin/env python3

import frappe
import argparse
import sys
from pathlib import Path

def search_and_replace_in_database(site_name: str, search_str: str, replace_str: str, dry_run: bool = False, verbose: bool = False):
    """
    Search and replace text in all varchar/text columns across the database.

    Args:
        search_str: String to search for
        replace_str: String to replace with
        dry_run: If True, only show what would be changed without making changes
    """
    # Check if search string equals replace string
    if search_str == replace_str:
        print(f"Search string '{search_str}' is identical to replace string - no changes needed")
        return
    frappe.connect(site=site_name)
    database_name = frappe.conf.db_name

    # Get all tables and columns with 'varchar' or 'text' data types
    query = """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = %s
        AND data_type IN ('varchar', 'text');
    """
    columns = frappe.db.sql(query, (database_name,), as_dict=True)

    # Track statistics
    total_matches = 0
    affected_tables = set()
    affected_columns = set()
    matches_by_table = {}

    for column in columns:
        table = column["table_name"]
        column_name = column["column_name"]

        # Find occurrences of the search string
        select_query = f"""
            SELECT `{column_name}`, COUNT(*) as match_count
            FROM `{table}`
            WHERE `{column_name}` LIKE %s;
        """
        rows = frappe.db.sql(select_query, (f"%{search_str}%",))

        if rows and rows[0][1] > 0:
            match_count = rows[0][1]
            if match_count > 0:
                total_matches += match_count
                affected_tables.add(table)
                affected_columns.add(f"{table}.{column_name}")
                
                if table not in matches_by_table:
                    matches_by_table[table] = 0
                matches_by_table[table] += match_count
                if dry_run:
                    print(f"Found {match_count} matches in {table}.{column_name}")
                else:
                    # Get and store sample values with their replacements before making changes
                    sample_query = f"""
                        SELECT `{column_name}`
                        FROM `{table}`
                        WHERE `{column_name}` LIKE %s
                        LIMIT 3;
                    """
                    before_values = frappe.db.sql(sample_query, (f"%{search_str}%",))
                    
                    # Calculate what the values will be after replacement
                    after_values = []
                    for before, in before_values:
                        after_values.append((before.replace(search_str, replace_str),))
                    
                    # Perform the replacement
                    update_query = f"""
                        UPDATE `{table}`
                        SET `{column_name}` = REPLACE(`{column_name}`, %s, %s)
                        WHERE `{column_name}` LIKE %s;
                    """
                    frappe.db.sql(update_query, (search_str, replace_str, f"%{search_str}%"))
                    frappe.db.commit()
                    
                    if verbose:
                        for i, (before,) in enumerate(before_values):
                            after = after_values[i][0] if i < len(after_values) else 'N/A'
                            print(f"[{table}.{column_name}] {before} -> {after}")

    if total_matches > 0:
        summary = []
        summary.append(f"\nSearch/Replace Summary:")
        summary.append(f"'{search_str}' -> '{replace_str}'")
        summary.append(f"Total {'matches' if dry_run else 'replacements'}: {total_matches}")
        if dry_run:
            summary.append("(Dry run - no changes made)")
        print("\n".join(summary))
        
        frappe.msgprint(f"{'Found' if dry_run else 'Replaced'} {total_matches} occurrences")
    else:
        print(f"No occurrences of '{search_str}' found")
        frappe.msgprint("No matches found")

def main():
    parser = argparse.ArgumentParser(
        description="Search and replace text across all text fields in the Frappe database"
    )
    parser.add_argument("site", help="Frappe site name (e.g. mysite.localhost)")
    parser.add_argument("search", help="Text to search for")
    parser.add_argument("replace", help="Text to replace with")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making changes"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output including before/after values"
    )

    args = parser.parse_args()

    # Verify site exists
    import frappe.utils
    bench_path = frappe.utils.get_bench_path()
    site_path = Path(bench_path) / "sites" / args.site

    if not site_path.exists():
        print(f"Error: Site '{args.site}' not found in bench sites directory: {site_path}", file=sys.stderr)
        sys.exit(1)

    search_and_replace_in_database(args.site, args.search, args.replace, args.dry_run, args.verbose)

if __name__ == "__main__":
    main()

