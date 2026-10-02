"""The migration chain must build from nothing.

The media tracker ran for 145 revisions with a chain that could not: its
initial revision aborted its transaction on an empty database and rolled back
to zero tables, unnoticed because the test fixtures built their schema with
create_all and never ran Alembic. This test is what makes that impossible here,
and it is written before there is a single table to build.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

# `models` is imported for its side effect, and the completeness assertion below
# depends on it entirely: `Base.metadata.tables` is empty unless the model
# modules have been imported, and the assertion would then compare against an
# empty set and pass no matter what shipped.
from app import models  # noqa: F401
from app.database import Base
from tests.conftest import admin_url, head_revision

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def scratch_database():
    """A database created for this test and dropped afterwards."""
    admin = create_engine(admin_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS travel_migration_test"))
        conn.execute(text("CREATE DATABASE travel_migration_test"))
    yield admin_url("travel_migration_test")
    # WITH (FORCE) because the test reads the scratch database back, and a
    # failed assertion leaves that connection open - a plain DROP would then
    # fail in teardown and bury the assertion that actually matters under an
    # unrelated error.
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS travel_migration_test WITH (FORCE)"))


def test_upgrade_head_runs_against_an_empty_database(scratch_database):
    env = dict(os.environ)
    env["DATABASE_URL"] = scratch_database
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    # A return code on its own says nothing about WHERE the run landed: a run
    # that ignored DATABASE_URL and migrated the developer's real `travel`
    # database would exit 0 just the same. Reading the scratch database back is
    # what pins it.
    engine = create_engine(scratch_database)
    with engine.connect() as conn:
        stamped = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        # The head specifically, not merely some revision: a run that stopped
        # part-way through the chain would still leave a plausible-looking row.
        assert stamped == head_revision()

        # Written while it was still vacuous, so that it would already be in
        # place on the day the first table was declared. It bites now: a
        # revision that forgets a table the models declare fails here.
        tables = set(inspect(conn).get_table_names())
        assert tables >= set(Base.metadata.tables), set(Base.metadata.tables) - tables
    engine.dispose()


def test_there_is_exactly_one_head():
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 1, result.stdout
    assert head_revision() in lines[0], result.stdout


def test_the_chain_downgrades_to_base_and_back(scratch_database):
    env = {**os.environ, "DATABASE_URL": scratch_database}

    def alembic(*command):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *command],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    alembic("upgrade", "head")

    # Load-bearing: the downgrades that narrow `ck_label_option_kind` delete
    # the rows the narrower constraint would refuse. On an empty database those
    # DELETEs meet nothing, and a downgrade that forgot one would still pass.
    # One row of each kind a revision added makes the narrowing bite.
    engine = create_engine(scratch_database)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO label_option (kind, value) "
                "VALUES ('location', '彰化'), ('ticket_type', '電子')"
            )
        )
        seeded = conn.execute(
            text("SELECT count(*) FROM label_option WHERE kind IN ('location', 'ticket_type')")
        ).scalar()
    engine.dispose()
    assert seeded == 2

    alembic("downgrade", "base")
    alembic("upgrade", "head")


def test_the_kind_revision_maps_every_flag_combination_and_back(scratch_database):
    """Load-bearing seed: on an empty database the UPDATEs meet nothing and a
    wrong CASE would still pass. One row per row of the spec's mapping table."""
    env = {**os.environ, "DATABASE_URL": scratch_database}

    def alembic(*command):
        result = subprocess.run([sys.executable, "-m", "alembic", *command], cwd=ROOT,
                                env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

    alembic("upgrade", "t3rip0000003")
    engine = create_engine(scratch_database)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO packing_list (name, saved, template) VALUES "
            "('both', true, true), ('tpl', false, true), ('kept', true, false), ('plain', false, false)"
        ))
        conn.execute(text(
            "INSERT INTO trip (name, archived, template, archive_note) VALUES "
            "('both', true, true, null), ('tpl', false, true, null), "
            "('old', true, false, '早點訂'), ('plain', false, false, null)"
        ))

    alembic("upgrade", "k1ind0000001")
    expected = {"both": ("template", None), "tpl": ("template", None),
                "kept": ("saved", None), "plain": ("free", "unused"),
                "old": ("saved", None)}
    with engine.connect() as conn:
        for table in ("packing_list", "trip"):
            rows = conn.execute(text(f"SELECT name, kind, usage FROM {table}")).all()
            for name, kind, usage in rows:
                assert (kind, usage) == expected[name], (table, name)
        note = conn.execute(text("SELECT archive_note FROM trip WHERE name = 'old'")).scalar()
        assert note == "早點訂"

    alembic("downgrade", "t3rip0000003")
    with engine.connect() as conn:
        lists = dict(conn.execute(text("SELECT name, (saved, template)::text FROM packing_list")).all())
        trips = dict(conn.execute(text("SELECT name, (archived, template)::text FROM trip")).all())
    engine.dispose()
    # `both` comes back a template only: the 保存 half was not kept.
    assert lists == {"both": "(f,t)", "tpl": "(f,t)", "kept": "(t,f)", "plain": "(f,f)"}
    assert trips == {"both": "(f,t)", "tpl": "(f,t)", "old": "(t,f)", "plain": "(f,f)"}
