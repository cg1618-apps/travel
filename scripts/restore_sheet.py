"""Replace every table with the rows in the owner's Google Sheet.

    venv/Scripts/python.exe -m scripts.restore_sheet --dry-run
    venv/Scripts/python.exe -m scripts.restore_sheet --replace
    venv/Scripts/python.exe -m scripts.restore_sheet --sheet-id <id> --replace

Reads the restore tabs only, never the readable ones. Refuses, writing
nothing, when the sheet was backed up at another Alembic revision, when a tab
is missing, or when the database holds rows and --replace was not passed. One
transaction: any error rolls it all back, and --dry-run rolls back on purpose.
In production it runs inside the container. See docs/sheet-backup.md.
"""

import argparse
import sys

from app.database import SessionLocal
from app.services.sheet_backup.client import (
    SheetsNotConfigured,
    SheetsUnavailable,
    open_spreadsheet,
)
from app.services.sheet_backup.format import CellRefused
from app.services.sheet_backup.restore import RestoreRefused, run_restore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--replace", action="store_true",
                        help="delete every row in the database first")
    parser.add_argument("--dry-run", action="store_true",
                        help="do everything, print the counts, and roll back")
    parser.add_argument("--sheet-id", help="restore from this sheet instead of GOOGLE_SHEET_ID")
    args = parser.parse_args(argv)

    try:
        client = open_spreadsheet(args.sheet_id)
        with SessionLocal() as db:
            result = run_restore(db, client, replace=args.replace, dry_run=args.dry_run)
    except RestoreRefused as refused:
        print(f"refused: {refused}", file=sys.stderr)
        for table, count in (refused.counts or {}).items():
            print(f"  {table}: {count}", file=sys.stderr)
        return 1
    except (CellRefused, SheetsNotConfigured, SheetsUnavailable) as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 1

    if any(result.replaced.values()):
        print("replaced:")
        for table, count in result.replaced.items():
            print(f"  {table}: {count}")
    print("restored:")
    for table, count in result.rows.items():
        print(f"  {table}: {count}")
    print("dry run: nothing written" if result.dry_run else "committed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
