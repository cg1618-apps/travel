"""The release must come back: downgrade to `origin/main`'s revision and up again.

`test_migrations_build_the_schema.py` proves the chain builds forward from an
empty database, and that it survives a trip to `base` and back. Neither is
what a rollback of a release does. The platform's rollback ladder downgrades
to the revision the box was at before the deploy - the one `main` holds - and
then serves traffic from whatever that leaves. So this test does exactly that
on a scratch database, upgrades again, and compares the schema object by
object with the one it started from: "it ran" is not the property that
matters, "it returned to where it was" is.

Several revisions can land in one release when sessions work concurrently,
and one step back would leave every earlier one in it unexercised until the
day it is needed. When this checkout holds no revision beyond `main`, or
`origin/main` cannot be read, it falls back to one step (`-1`), the most it
can honestly check.

The media tracker's `tests/api/test_migration_round_trip.py` is the shape
this follows. It also walks an `irreversible = True` marker; no travel
revision declares one and `deploy/migrations` reads none, so neither does
this.
"""

import subprocess
import warnings
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import text

from alembic.config import Config
from alembic.script import ScriptDirectory
from tests import databases
from tests.api.conftest import run_alembic

ROOT = Path(__file__).resolve().parents[2]
VERSIONS = "alembic/versions/"
ONE_STEP = "-1"

# Every named object and every column. Indexes, constraints and sequences are
# the families a careless downgrade drops and an upgrade fails to put back.
SCHEMA_SQL = text(
    """
    SELECT 'seq:' || sequencename FROM pg_sequences WHERE schemaname = 'public'
    UNION ALL
    SELECT 'con:' || conname || ':' || pg_get_constraintdef(oid) FROM pg_constraint
      WHERE connamespace = 'public'::regnamespace
    UNION ALL
    SELECT 'ix:' || indexname || ':' || indexdef FROM pg_indexes WHERE schemaname = 'public'
    UNION ALL
    SELECT 'col:' || table_name || '.' || column_name || ':' || data_type || ':'
           || is_nullable || ':' || coalesce(column_default, '-')
      FROM information_schema.columns WHERE table_schema = 'public'
    """
)


def release_downgrade_target(head: str, parent: dict[str, str | None], on_main: set[str]) -> str:
    """Where a rollback of this release would downgrade to.

    Walks down from `head` through every revision `main` does not hold and
    stops at the first one it does: main's head, the release's base. When
    `head` is itself on main the release adds nothing, and the range is one
    step. A chain `main` holds none of goes all the way to `base`.
    """
    if head in on_main:
        return ONE_STEP
    revision = head
    while revision not in on_main:
        below = parent[revision]
        if below is None:
            return "base"
        revision = below
    return revision


def _main_revision_files() -> set[str] | None:
    """Basenames of the revision files on `origin/main`, or None if unreadable.

    CI checks out with `fetch-depth: 0`, which brings every branch, so
    `origin/main` is there; a laptop has it after any `git fetch`. None is
    the shallow-checkout case, and the caller says so rather than passing
    quietly on less than it claims.
    """
    result = subprocess.run(
        ["git", "ls-tree", "--name-only", "origin/main", VERSIONS],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return {Path(line).name for line in result.stdout.splitlines()}


def _release_range() -> tuple[str, str]:
    """(head, target) for this checkout against origin/main."""
    script = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
    (head,) = script.get_heads()
    on_main_files = _main_revision_files()
    if on_main_files is None:
        warnings.warn(
            "origin/main cannot be read; the round trip falls back to one step. "
            "`git fetch origin main` to check the whole release.",
            stacklevel=2,
        )
        return head, ONE_STEP
    parent, on_main = {}, set()
    for rev in script.walk_revisions():
        assert not isinstance(rev.down_revision, tuple), f"merge revision {rev.revision}"
        parent[rev.revision] = rev.down_revision
        if Path(rev.path).name in on_main_files:
            on_main.add(rev.revision)
    return head, release_downgrade_target(head, parent, on_main)


def _schema(database: str) -> set[str]:
    engine = sa.create_engine(databases.server_url(database))
    try:
        with engine.connect() as conn:
            return set(conn.execute(SCHEMA_SQL).scalars())
    finally:
        engine.dispose()


def test_the_release_survives_a_downgrade_and_a_second_upgrade(scratch_database):
    """head -> the release's base -> head, against a real database."""
    head, target = _release_range()

    upgraded = run_alembic(scratch_database, "upgrade", "head")
    assert upgraded.returncode == 0, upgraded.stderr
    before = _schema(scratch_database)
    # Not vacuous: an empty snapshot compares equal to another empty one.
    assert len(before) > 50, "the migrated schema is nearly empty; this check is vacuous"

    down = run_alembic(scratch_database, "downgrade", target)
    assert down.returncode == 0, (
        f"downgrading from {head} to {target} failed - a rollback of this "
        f"release would fail the same way.\n{down.stderr[-3000:]}"
    )
    again = run_alembic(scratch_database, "upgrade", "head")
    assert again.returncode == 0, again.stderr

    after = _schema(scratch_database)
    assert after == before, (
        "the round trip did not restore the schema.\n"
        f"lost: {sorted(before - after)}\n"
        f"gained: {sorted(after - before)}"
    )


# A chain a <- b <- c <- d. Pure: no database, no git.
CHAIN = {"a": None, "b": "a", "c": "b", "d": "c"}


@pytest.mark.parametrize(
    ("head", "on_main", "expected"),
    [
        # The release adds c and d: both downgrades run, back to main's head.
        ("d", {"a", "b"}, "b"),
        # The release adds d alone: main's head is d's parent.
        ("d", {"a", "b", "c"}, "c"),
        # Nothing beyond main: one step.
        ("b", {"a", "b"}, ONE_STEP),
        # main holds none of the chain: the whole of it comes back.
        ("d", set(), "base"),
    ],
)
def test_the_release_range_is_what_a_rollback_would_undo(head, on_main, expected):
    assert release_downgrade_target(head, CHAIN, on_main) == expected
