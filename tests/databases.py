"""Test databases: one per run, one per scratch use, none with a fixed name.

The platform's rule (`docs/registry.md`, "How an app's tests use the shared
server"): what makes two test runs collide is a shared database NAME, not the
shared server. So every database a test touches is created here under a name
nobody else can hold, and dropped when its user is done with it. The name is
never read from `.env`: only the server and the credentials are.

Names are `travel_test_<epoch>_<hex>`, the shape the media tracker's
`tests/databases.py` uses. The epoch is part of the unique suffix and is what
makes leftover cleanup safe: a database with no connections is only dropped
once it is older than LEFTOVER_AGE, so a run that has just created its
database and not yet connected to it - the moment between `CREATE DATABASE`
and the `alembic upgrade` subprocess opening its connection - cannot lose it
to a neighbour's cleanup.
"""

import re
import time
import uuid
from contextlib import contextmanager

import sqlalchemy as sa
from sqlalchemy import text

PREFIX = "travel_test"
LEFTOVER_AGE = 2 * 60 * 60  # seconds
_NAME = re.compile(rf"^{PREFIX}_(\d+)_[0-9a-f]+$")


def new_name() -> str:
    """A database name no other run or test can be using."""
    return f"{PREFIX}_{int(time.time())}_{uuid.uuid4().hex[:12]}"


def server_url(database: str) -> str:
    """The app's own configured server, pointed at one named database.

    Derived from `settings` rather than hardcoding a superuser password, which
    is per-machine and not something a test should know. The tests then work
    wherever the app itself would.

    `render_as_string(hide_password=False)` rather than `str()`: SQLAlchemy's
    URL.__str__ masks the password as `***`, so str() hands back a URL that
    connects to the right host as the right user and fails authentication.
    """
    from app.config import settings

    url = sa.engine.url.make_url(settings.sqlalchemy_database_url)
    if url.host == "localhost":
        # A machine's .env may still name `localhost`. On Windows that
        # resolves to ::1 first, the development database listens on
        # 127.0.0.1 only, and every new connection - each alembic
        # subprocess, each engine - waited 21 seconds before falling back.
        url = url.set(host="127.0.0.1")
    return url.set(database=database).render_as_string(hide_password=False)


def _admin() -> sa.Engine:
    return sa.create_engine(server_url("postgres"), isolation_level="AUTOCOMMIT")


def create(name: str) -> None:
    assert _NAME.match(name), f"not a test database name: {name!r}"
    admin = _admin()
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        admin.dispose()


def drop(name: str) -> None:
    """Drop one test database, ending any session still connected to it.

    WITH (FORCE) because a test that fails an assertion can leave a
    connection open, and a plain DROP would then fail in teardown and bury the
    assertion that matters under an unrelated error.
    """
    assert _NAME.match(name), f"refusing to drop a non-test database: {name!r}"
    admin = _admin()
    try:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    finally:
        admin.dispose()


def drop_leftovers(now: float | None = None) -> list[str]:
    """Drop test databases a crashed or interrupted run left behind.

    Only names this module mints, only with no connections, and only once
    older than LEFTOVER_AGE - a database with connections, or a young one,
    belongs to a run in progress and is left alone.
    """
    now = time.time() if now is None else now
    admin = _admin()
    dropped = []
    try:
        with admin.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT d.datname FROM pg_database d "
                    "WHERE d.datname LIKE :prefix AND NOT EXISTS ("
                    "  SELECT 1 FROM pg_stat_activity a WHERE a.datname = d.datname)"
                ),
                {"prefix": f"{PREFIX}\\_%"},
            ).scalars()
            for name in rows:
                match = _NAME.match(name)
                if match and now - int(match.group(1)) > LEFTOVER_AGE:
                    conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
                    dropped.append(name)
    finally:
        admin.dispose()
    return dropped


@contextmanager
def scratch():
    """A fresh, empty database for one use, dropped afterwards whatever happens."""
    name = new_name()
    create(name)
    try:
        yield name
    finally:
        drop(name)
