"""The database-backed fixtures, and the one decision that makes them worth having.

**The schema here is built by running Alembic, not by `Base.metadata.create_all`.**

That is a deliberate divergence from the media tracker, whose
`tests/api/conftest.py` builds its schema from the ORM models directly — and
whose own baseline migration records what that cost: 145 revisions on a chain
that could not build from nothing, because the models were right, the
migrations were wrong, and no test could tell the difference. A fixture is the
only place that mistake is invisible, so this one runs the real command and
`test_the_fixture_runs_migrations.py` asserts that it did.

The cost is honest and small: the session pays one `alembic upgrade head`, and
a migration that does not run is a suite that does not start rather than a
drift nobody notices for four months.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import get_db
from tests import databases

ROOT = Path(__file__).resolve().parents[2]


def run_alembic(database: str, *command: str) -> subprocess.CompletedProcess:
    """The real `alembic` command as a subprocess, pointed at one database.

    `alembic/env.py` reads the URL from `app.config.settings` at import, so an
    already-running test process cannot repoint it; `DATABASE_URL` in the
    child's environment can, because the app honours it verbatim. A
    subprocess is also what a human runs.
    """
    return subprocess.run(
        [sys.executable, "-m", "alembic", *command],
        cwd=ROOT,
        env={**os.environ, "DATABASE_URL": databases.server_url(database)},
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="session")
def _leftovers_swept():
    """Drop what crashed runs left behind, once, before this run creates any.

    Every database fixture below depends on this, so the sweep happens the
    first time a run touches PostgreSQL - and the unit tier, which never
    does, needs no server at all.
    """
    databases.drop_leftovers()


@pytest.fixture(scope="session")
def migrated_database(_leftovers_swept):
    """This run's own database, built by `alembic upgrade head` and dropped
    `WITH (FORCE)` when the session ends. Its name is minted for the run
    (`tests/databases.py`), so a second run - another worktree, another
    session - builds its own rather than dropping this one."""
    with databases.scratch() as name:
        result = run_alembic(name, "upgrade", "head")
        # Loud rather than mysterious: without this, a failed migration
        # surfaces as every test in the directory failing on a missing table.
        assert result.returncode == 0, result.stderr
        yield databases.server_url(name)


@pytest.fixture
def scratch_database(_leftovers_swept):
    """One empty database for a test that builds its own chain, dropped after."""
    with databases.scratch() as name:
        yield name


@pytest.fixture(scope="session")
def engine(migrated_database):
    engine = create_engine(migrated_database)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(engine):
    """A session inside a transaction that is rolled back when the test ends.

    Rollback rather than deleting rows between tests: it is faster, it cannot
    miss a table somebody adds later, and it leaves the migrated schema exactly
    as the migrations built it.
    """
    connection = engine.connect()
    transaction = connection.begin()
    # `join_transaction_mode="create_savepoint"` is what makes this work once
    # the routers start committing. Without it a request's `db.commit()` ends
    # the transaction opened above, the rollback in teardown has nothing left
    # to undo, and rows leak between tests - which shows up as a test that
    # passes alone and fails in a suite, days later.
    session = Session(
        bind=connection, autoflush=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        session.close()
        # A test that asserts a constraint REFUSES leaves the transaction
        # already aborted, and rolling back an inactive one warns. Guarding
        # keeps the refusal tests - which are most of the value here - from
        # filling the run with noise that trains people to ignore warnings.
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session):
    """A TestClient whose requests run in the test's own transaction."""
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
