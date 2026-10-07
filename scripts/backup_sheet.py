"""Back the database up to the owner's Google Sheet.

    venv/Scripts/python.exe -m scripts.backup_sheet

The same backup as the 備份 button, for the nightly timer
(deploy/backup/sheets.sh, inside the container) and for running by hand.
Exits non-zero on any refusal or failure, so the timer's failure is seen. See
docs/sheet-backup.md.
"""

import argparse
import sys

from app.database import SessionLocal
from app.services.sheet_backup.backup import BackupAlreadyRunning, NothingToBackUp, run_backup
from app.services.sheet_backup.client import (
    SheetsNotConfigured,
    SheetsUnavailable,
    open_spreadsheet,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args(argv)

    try:
        client = open_spreadsheet()
        with SessionLocal() as db:
            result = run_backup(db, client)
    except (SheetsNotConfigured, SheetsUnavailable, BackupAlreadyRunning,
            NothingToBackUp) as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 1

    print(f"backed up at {result.backed_up_at.isoformat()} into {result.tabs} tabs")
    for table, count in result.rows.items():
        print(f"  {table}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
