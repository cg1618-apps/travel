"""Write the whole database, and the readable tabs, to the owner's sheet.

One request, not a stream: about a dozen tab writes batched into a handful of
calls finish in seconds, well inside the tunnel's 100-second limit, which is
the only reason media's backup streams. The order of work is what keeps a
failure harmless:

1. refuse an all-empty database before anything is read from Google - that
   is a worktree's empty database or the wrong DATABASE_URL, and writing it
   would blank the owner's only off-box copy;
2. write every tab in one batch, and only then trim what lies beyond it;
3. link 總覽 to the tabs, delete stale readable tabs, put the tabs in order.

One table at zero rows while others hold some is ordinary - the last route
deleted - and its tab is written header-only.

A failure in step 2 leaves the previous backup standing. A failure in step 3
leaves a complete backup with an untidy front page, which the next run fixes.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, selectinload

from app.models import TransportOption, TransportRoute
from app.routers.health import read_alembic_revision
from app.services.domain.dashboard import readable_set
from app.services.sheet_backup import readable
from app.services.sheet_backup.client import SheetClient
from app.services.sheet_backup.format import to_sheet
from app.services.sheet_backup.tabs import BACKUP_INFO, RESTORE_TABS

logger = logging.getLogger(__name__)

# One backup at a time, across every process on the database: the web app and
# the nightly `deploy/backup/sheets.sh`, which runs in a process of its own.
# Two writers on one sheet each trim what the other wrote. A SESSION-level
# advisory lock on a connection of its own, as media's: PostgreSQL drops it
# with the connection if the process dies, so it can never be left stale.
# Distinct from media's 1618_0001 - this is travel's port - so the two can
# never be confused in `pg_locks`, though they live in different databases.
BACKUP_LOCK_KEY = 1618_8002


class BackupAlreadyRunning(RuntimeError):
    """Another backup holds the sheet; this one was refused before writing."""


class NothingToBackUp(RuntimeError):
    """Every table is empty, so this is almost certainly the wrong database."""


@dataclass(frozen=True)
class BackupResult:
    tabs: int
    rows: dict[str, int]
    backed_up_at: datetime


class BackupClaim:
    """The held advisory lock. `release()` is idempotent."""

    def __init__(self, connection):
        self._connection = connection

    def release(self) -> None:
        connection, self._connection = self._connection, None
        if connection is None:
            return
        try:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": BACKUP_LOCK_KEY})
        except Exception:
            # Returned to the pool still holding the lock, the connection would
            # refuse every backup until it was recycled; throw it away instead,
            # and PostgreSQL releases the lock as it closes.
            logger.exception("Could not release the backup lock; discarding its connection.")
            connection.invalidate()
        finally:
            connection.close()


def claim_backup(engine: Engine) -> BackupClaim:
    connection = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        held = connection.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": BACKUP_LOCK_KEY}
        ).scalar()
    except Exception:
        connection.close()
        raise
    if not held:
        connection.close()
        raise BackupAlreadyRunning("A backup is already running.")
    return BackupClaim(connection)


def count_rows(db: Session) -> dict[str, int]:
    """Every table's row count, by table name, in restore order."""
    return {
        tab.table.name: db.scalar(select(func.count()).select_from(tab.table))
        for tab in RESTORE_TABS
    }


def restore_matrix(db: Session, tab) -> list[list[str]]:
    """Header row of column names, then every row by `id`, every column."""
    columns = list(tab.table.columns)
    rows = db.execute(select(tab.table).order_by(tab.table.c.id)).all()
    return [
        [column.name for column in columns],
        *([to_sheet(row._mapping[column]) for column in columns] for row in rows),
    ]


def run_backup(db: Session, client: SheetClient, *, now: datetime | None = None) -> BackupResult:
    """Back the database up into `client`'s spreadsheet.

    Raises BackupAlreadyRunning while another backup holds the lock,
    NothingToBackUp for an all-empty database, and SheetsUnavailable when Google cannot be
    reached. Never writes to the database.
    """
    # The lock is taken on the engine the session reads through, so it lives in
    # the same database as the data it guards - the test database in the suite.
    claim = claim_backup(db.get_bind().engine)
    try:
        return _write_backup(db, client, now or datetime.now(timezone.utc))
    finally:
        claim.release()


def _write_backup(db: Session, client: SheetClient, backed_up_at: datetime) -> BackupResult:
    rows = count_rows(db)
    if not any(rows.values()):
        raise NothingToBackUp(
            "Every table is empty. This is not the database the sheet backs up, "
            "so nothing was written."
        )

    matrices: dict[str, list[list]] = {}

    lists, trips = readable_set(db)
    list_titles = readable.tab_titles(readable.LIST_PREFIX, lists)
    trip_titles = readable.tab_titles(readable.TRIP_PREFIX, trips)
    readable_titles = [
        *(list_titles[row.id] for row in lists),
        *(trip_titles[row.id] for row in trips),
        readable.TRANSPORT,
    ]
    overview, links = readable.overview_matrix(backed_up_at, readable_titles)
    matrices[readable.OVERVIEW] = overview
    for row in lists:
        matrices[list_titles[row.id]] = readable.list_matrix(row)
    for row in trips:
        matrices[trip_titles[row.id]] = readable.trip_matrix(row)
    routes = db.scalars(
        select(TransportRoute).options(
            selectinload(TransportRoute.options).selectinload(TransportOption.departures)
        )
    ).all()
    matrices[readable.TRANSPORT] = readable.transport_matrix(list(routes))

    matrices[BACKUP_INFO] = [
        ["key", "value"],
        ["backed_up_at", to_sheet(backed_up_at)],
        ["alembic_revision", read_alembic_revision(db) or ""],
        *([table, str(count)] for table, count in rows.items()),
    ]
    for tab in RESTORE_TABS:
        matrices[tab.name] = restore_matrix(db, tab)

    client.overwrite(matrices)

    tabs = client.worksheets()
    client.write_formulas(
        readable.OVERVIEW,
        {f"A{link.row}": readable.hyperlink(tabs[link.title].id, link.title) for link in links},
    )
    stale = [
        title for title in tabs
        if readable.is_readable_title(title) and title not in matrices
    ]
    client.delete_tabs(stale)
    client.reorder([
        readable.OVERVIEW,
        *readable_titles,
        BACKUP_INFO,
        *(tab.name for tab in RESTORE_TABS),
    ])

    logger.info("Backed up %s rows into %s tabs; deleted %s stale tabs",
                sum(rows.values()), len(matrices), len(stale))
    return BackupResult(tabs=len(matrices), rows=rows, backed_up_at=backed_up_at)
