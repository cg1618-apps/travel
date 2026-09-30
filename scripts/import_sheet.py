"""Load the owner's travel sheet into this app's database.

    venv/Scripts/python.exe -m scripts.import_sheet export.xlsx --trip-start 2026-09-24 --dry-run

Reads only the four tabs named in app/services/sheet_import/parse.py. The
export carries booking codes: keep it out of the repository. See
docs/sheet-import.md.
"""

import argparse
import sys
from datetime import date

import openpyxl

from app.database import SessionLocal
from app.services.sheet_import.parse import parse_workbook
from app.services.sheet_import.write import ImportClash, write_sheet


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path")
    parser.add_argument("--trip-start", type=date.fromisoformat, required=True)
    parser.add_argument("--trip-name", default="彰化 ⇄ 台北")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    sheet = parse_workbook(
        openpyxl.load_workbook(args.path), trip_start=args.trip_start, trip_name=args.trip_name
    )
    print(f"{len(sheet.lists)} lists, {sum(len(row.items) for row in sheet.lists)} items, "
          f"{len(sheet.routes)} routes, {len(sheet.trip.legs)} legs")
    for line in sheet.report:
        print(f"  note: {line}")

    with SessionLocal() as db:
        try:
            write_sheet(db, sheet)
        except ImportClash as clash:
            for line in clash.clashes:
                print(f"  refused: {line}", file=sys.stderr)
            return 1
        if args.dry_run:
            db.rollback()
            print("dry run: nothing written")
        else:
            db.commit()
            print("imported")
    return 0


if __name__ == "__main__":
    sys.exit(main())
