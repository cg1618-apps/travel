"""Rebuild the database from the sheet's restore tabs. Replaces; never merges.

Media upserts, which cannot remove a row deleted since the backup. travel is
one person's data and the backup is the whole truth, so a restore deletes all
eight tables and inserts every row with its original `id` - which is also why
plain integer ids are enough here and nothing needs a stable public key.

Everything is read and checked before anything is deleted, and all of it runs
in one transaction: any refusal or error rolls the whole thing back, and a
dry run rolls back on purpose. The readable tabs are never read.
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy import Table, delete, func, insert, select, text
from sqlalchemy.orm import Session

from app.routers.health import read_alembic_revision
from app.services.sheet_backup.backup import count_rows
from app.services.sheet_backup.client import SheetClient
from app.services.sheet_backup.format import CellRefused, from_sheet
from app.services.sheet_backup.tabs import BACKUP_INFO, RESTORE_TABS, RestoreTab

logger = logging.getLogger(__name__)


class RestoreRefused(RuntimeError):
    """The restore would be wrong or destructive; nothing was written.

    `counts` is set when the refusal is a database that already holds rows,
    so the caller can show exactly what `--replace` would delete.
    """

    def __init__(self, message: str, counts: dict[str, int] | None = None):
        super().__init__(message)
        self.counts = counts


@dataclass
class RestoreResult:
    rows: dict[str, int]
    replaced: dict[str, int] = field(default_factory=dict)
    dry_run: bool = False


def run_restore(
    db: Session, client: SheetClient, *, replace: bool = False, dry_run: bool = False
) -> RestoreResult:
    """Replace every table with the sheet's rows, or refuse and write nothing.

    Commits on success, rolls back on a dry run and on any error. Refuses
    (RestoreRefused) when a restore tab or Backup Info is missing, when the
    sheet was written at another Alembic revision, when the database holds
    rows and `replace` is false, and (CellRefused) when a cell cannot be
    stored in its column.
    """
    try:
        result = _restore(db, client, replace=replace)
    except Exception:
        db.rollback()
        raise
    if dry_run:
        db.rollback()
        result.dry_run = True
    else:
        db.commit()
    return result


def _restore(db: Session, client: SheetClient, *, replace: bool) -> RestoreResult:
    names = [BACKUP_INFO, *(tab.name for tab in RESTORE_TABS)]
    present = client.worksheets()
    missing = [name for name in names if name not in present]
    if missing:
        raise RestoreRefused(f"The sheet has no {', '.join(missing)} tab; nothing was restored.")

    values = client.read(names)
    info = _backup_info(values[BACKUP_INFO])

    sheet_revision = info.get("alembic_revision", "")
    db_revision = read_alembic_revision(db)
    if sheet_revision != db_revision:
        raise RestoreRefused(
            f"The sheet was backed up at revision {sheet_revision or '(none)'}, and this "
            f"database is at {db_revision or '(none)'}. Migrate first, or restore into a "
            "database at the sheet's revision."
        )

    existing = count_rows(db)
    if any(existing.values()) and not replace:
        raise RestoreRefused(
            "The database is not empty; pass --replace to delete these rows and restore.",
            counts=existing,
        )

    # Every tab is parsed before a single row is deleted, so a bad cell on the
    # last tab refuses the restore rather than leaving it half done.
    parsed = {tab.name: _parse_tab(tab, values[tab.name]) for tab in RESTORE_TABS}
    for tab in RESTORE_TABS:
        expected = info.get(tab.table.name)
        if expected is not None and expected != str(len(parsed[tab.name])):
            raise RestoreRefused(
                f"{tab.name} holds {len(parsed[tab.name])} rows but Backup Info says "
                f"{expected}: the backup did not finish writing. Nothing was restored."
            )

    for tab in reversed(RESTORE_TABS):
        db.execute(delete(tab.table))
    for tab in RESTORE_TABS:
        if parsed[tab.name]:
            db.execute(insert(tab.table), parsed[tab.name])
    for tab in RESTORE_TABS:
        _restart_sequence(db, tab.table)
    db.flush()

    rows = {tab.table.name: len(parsed[tab.name]) for tab in RESTORE_TABS}
    logger.info("Restored %s rows from the sheet", sum(rows.values()))
    return RestoreResult(rows=rows, replaced=existing)


def _backup_info(matrix: list[list[str]]) -> dict[str, str]:
    """Backup Info's key/value rows as a dict; the header row is skipped."""
    return {row[0]: (row[1] if len(row) > 1 else "") for row in matrix[1:] if row and row[0]}


def _parse_tab(tab: RestoreTab, matrix: list[list[str]]) -> list[dict]:
    """The tab's rows as column-name dicts, every column present, or a refusal.

    Columns are matched by header NAME, never by position. A header the table
    has no column for is refused, as is a missing header for a column that
    cannot be null; a missing nullable column restores as null. A wholly blank
    row is skipped - it is a gap, not a row of nulls.
    """
    if not matrix:
        raise RestoreRefused(f"{tab.name} is empty: it has no header row.")
    columns = {column.name: column for column in tab.table.columns}
    headers = matrix[0]
    positions: dict[str, int] = {}
    for index, header in enumerate(headers):
        if header == "" and all(row[index] == "" for row in matrix[1:]):
            continue
        if header not in columns:
            raise CellRefused(tab.name, 1, header or f"#{index + 1}", "no such column")
        if header in positions:
            raise CellRefused(tab.name, 1, header, "appears twice")
        positions[header] = index
    for name, column in columns.items():
        if name not in positions and not column.nullable:
            raise CellRefused(tab.name, 1, name, "is missing, and cannot be null")

    rows = []
    for number, cells in enumerate(matrix[1:], start=2):
        if all(cell == "" for cell in cells):
            continue
        row = {}
        for name, column in columns.items():
            cell = cells[positions[name]] if name in positions else ""
            try:
                value = from_sheet(column, cell)
            except ValueError as error:
                raise CellRefused(tab.name, number, name, str(error)) from None
            if value is None and not column.nullable:
                raise CellRefused(tab.name, number, name, "is empty, and cannot be null")
            row[name] = value
        rows.append(row)
    return rows


def _restart_sequence(db: Session, table: Table) -> None:
    """Point the id sequence past the highest restored id.

    PostgreSQL does not advance a sequence for an id supplied explicitly, so
    after a restore the next insert would collide with row 1. The ids are
    `serial` columns, and `pg_get_serial_sequence` names their sequence.
    `ALTER SEQUENCE ... RESTART` rather than `setval`, because `setval` is not
    transactional: a dry run or a failed restore would roll the rows back and
    leave the sequence moved.
    """
    sequence = db.scalar(text("SELECT pg_get_serial_sequence(:table, 'id')"), {"table": table.name})
    next_id = int(db.scalar(select(func.coalesce(func.max(table.c.id), 0)))) + 1
    # The name comes from the catalog, already quoted where it needs to be; the
    # number is an int. DDL takes no bind parameters, hence the f-string.
    db.execute(text(f"ALTER SEQUENCE {sequence} RESTART WITH {next_id}"))
