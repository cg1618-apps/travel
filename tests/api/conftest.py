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
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.database import get_db
from tests.conftest import admin_url

ROOT = Path(__file__).resolve().parents[2]

# Distinct from the from-zero test's `travel_migration_test`, which that test
# drops and recreates mid-session. Sharing one database between the two would
# pull the schema out from under every test in this directory.
TEST_DATABASE = "travel_test"


@pytest.fixture(scope="session")
def migrated_database():
    """A database built by `alembic upgrade head`, dropped when the session ends."""
    admin = create_engine(admin_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DATABASE} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {TEST_DATABASE}"))

    url = admin_url(TEST_DATABASE)
    env = dict(os.environ)
    env["DATABASE_URL"] = url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    # Loud rather than mysterious: without this, a failed migration surfaces as
    # every test in the directory failing on a missing table.
    assert result.returncode == 0, result.stderr

    yield url

    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DATABASE} WITH (FORCE)"))
    admin.dispose()


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
    session = Session(bind=connection, autoflush=False)
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
