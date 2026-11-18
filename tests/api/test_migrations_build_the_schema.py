"""The migration chain must build from nothing.

The media tracker ran for 145 revisions with a chain that could not: its
initial revision aborted its transaction on an empty database and rolled back
to zero tables, unnoticed because the test fixtures built their schema with
create_all and never ran Alembic. This test is what makes that impossible here,
and it is written before there is a single table to build.
"""

import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from alembic.config import Config
from alembic.script import ScriptDirectory

# `models` is imported for its side effect, and the completeness assertion below
# depends on it entirely: `Base.metadata.tables` is empty unless the model
# modules have been imported, and the assertion would then compare against an
# empty set and pass no matter what shipped.
from app import models  # noqa: F401
from app.database import Base
from tests import databases
from tests.api.conftest import run_alembic
from tests.conftest import head_revision

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))


def migrate(database: str, *command: str) -> None:
    """Run the real `alembic` command against one scratch database, loudly."""
    result = run_alembic(database, *command)
    assert result.returncode == 0, result.stderr


def previous(revision: str) -> str:
    """The revision before `revision`, as Alembic's script directory says.

    Never written in as an id: reparenting a revision to fix two heads
    changes its parent, and a test holding the old id would then exercise
    the wrong step without failing.
    """
    down = SCRIPT.get_revision(revision).down_revision
    assert isinstance(down, str), f"{revision} has no single parent: {down!r}"
    return down


def test_upgrade_head_runs_against_an_empty_database(scratch_database):
    migrate(scratch_database, "upgrade", "head")

    # A return code on its own says nothing about WHERE the run landed: a run
    # that ignored DATABASE_URL and migrated the developer's real `travel`
    # database would exit 0 just the same. Reading the scratch database back is
    # what pins it.
    engine = create_engine(databases.server_url(scratch_database))
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
    migrate(scratch_database, "upgrade", "head")

    # Load-bearing: the downgrades that narrow `ck_label_option_kind` delete
    # the rows the narrower constraint would refuse. On an empty database those
    # DELETEs meet nothing, and a downgrade that forgot one would still pass.
    # One row of each kind a revision added makes the narrowing bite.
    engine = create_engine(databases.server_url(scratch_database))
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

    migrate(scratch_database, "downgrade", "base")
    migrate(scratch_database, "upgrade", "head")


def test_the_kind_revision_maps_every_flag_combination_and_back(scratch_database):
    """Load-bearing seed: on an empty database the UPDATEs meet nothing and a
    wrong CASE would still pass. One row per flag combination the revision maps."""
    migrate(scratch_database, "upgrade", previous("k1ind0000001"))
    engine = create_engine(databases.server_url(scratch_database))
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO packing_list (name, saved, template) VALUES "
                "('both', true, true), ('tpl', false, true), "
                "('kept', true, false), ('plain', false, false)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO trip (name, archived, template, archive_note) VALUES "
                "('both', true, true, null), ('tpl', false, true, null), "
                "('old', true, false, '早點訂'), ('plain', false, false, null)"
            )
        )

    migrate(scratch_database, "upgrade", "k1ind0000001")
    expected = {
        "packing_list": {
            "both": ("template", None),
            "tpl": ("template", None),
            "kept": ("saved", None),
            "plain": ("free", "unused"),
        },
        "trip": {
            "both": ("template", None),
            "tpl": ("template", None),
            "old": ("saved", None),
            "plain": ("free", "unused"),
        },
    }
    with engine.connect() as conn:
        for table, rows in expected.items():
            found = conn.execute(text(f"SELECT name, kind, usage FROM {table}")).all()
            assert {name: (kind, usage) for name, kind, usage in found} == rows, table
        note = conn.execute(text("SELECT archive_note FROM trip WHERE name = 'old'")).scalar()
        assert note == "早點訂"

    migrate(scratch_database, "downgrade", previous("k1ind0000001"))
    with engine.connect() as conn:
        lists = dict(
            conn.execute(text("SELECT name, (saved, template)::text FROM packing_list")).all()
        )
        trips = dict(conn.execute(text("SELECT name, (archived, template)::text FROM trip")).all())
        note = conn.execute(text("SELECT archive_note FROM trip WHERE name = 'old'")).scalar()
    engine.dispose()
    # `both` comes back a template only: the 保存 half was not kept.
    assert lists == {"both": "(f,t)", "tpl": "(f,t)", "kept": "(t,f)", "plain": "(f,f)"}
    assert trips == {"both": "(f,t)", "tpl": "(f,t)", "old": "(t,f)", "plain": "(f,f)"}
    assert note == "早點訂"


def test_the_packed_count_revision_turns_zero_into_no_value_and_back(scratch_database):
    """Load-bearing seed: a 0, a real count and (after the upgrade) a null.

    On an empty database the UPDATEs in both directions meet nothing, and a
    downgrade that forgot to fill the nulls would only fail on a row holding one.
    """
    migrate(scratch_database, "upgrade", previous("p3acking0003"))
    engine = create_engine(databases.server_url(scratch_database))
    with engine.begin() as conn:
        list_id = conn.execute(
            text("INSERT INTO packing_list (name, usage) VALUES ('l', 'unused') RETURNING id")
        ).scalar()
        conn.execute(
            text(
                "INSERT INTO packing_item (list_id, name, quantity_packed) VALUES "
                "(:list_id, 'uncounted', 0), (:list_id, 'counted', 3)"
            ),
            {"list_id": list_id},
        )

    migrate(scratch_database, "upgrade", "p3acking0003")
    with engine.begin() as conn:
        found = dict(conn.execute(text("SELECT name, quantity_packed FROM packing_item")).all())
        assert found == {"uncounted": None, "counted": 3}
        # No server default any more: an insert that names no count stores null.
        conn.execute(
            text("INSERT INTO packing_item (list_id, name) VALUES (:list_id, 'new')"),
            {"list_id": list_id},
        )
        new = conn.execute(
            text("SELECT quantity_packed FROM packing_item WHERE name = 'new'")
        ).scalar()
        assert new is None

    migrate(scratch_database, "downgrade", previous("p3acking0003"))
    with engine.connect() as conn:
        found = dict(conn.execute(text("SELECT name, quantity_packed FROM packing_item")).all())
        nullable = conn.execute(
            text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'packing_item' AND column_name = 'quantity_packed'"
            )
        ).scalar()
    engine.dispose()
    assert found == {"uncounted": 0, "counted": 3, "new": 0}
    assert nullable == "NO"


def test_the_entry_types_revision_backfills_and_refuses_to_invent_a_time(scratch_database):
    """Load-bearing seed: an existing leg and trip, so the backfill has rows to
    fill; then an untimed leg, so the downgrade has something to refuse on."""
    migrate(scratch_database, "upgrade", previous("t5rip0000005"))
    engine = create_engine(databases.server_url(scratch_database))
    with engine.begin() as conn:
        trip_id = conn.execute(
            text("INSERT INTO trip (name, usage) VALUES ('t', 'unused') RETURNING id")
        ).scalar()
        conn.execute(
            text(
                "INSERT INTO trip_leg (trip_id, from_place, to_place, departs_at, arrives_at) "
                "VALUES (:t, 'a', 'b', '2026-11-04 08:00+08', '2026-11-04 09:00+08')"
            ),
            {"t": trip_id},
        )

    migrate(scratch_database, "upgrade", "t5rip0000005")
    with engine.begin() as conn:
        leg = conn.execute(
            text(
                "SELECT transport_type, has_booked, has_paid, has_collected, has_booking_code, "
                "section FROM trip_leg"
            )
        ).one()
        assert tuple(leg) == ("other", True, True, True, True, None)
        trip = conn.execute(text("SELECT ticket_status, round_trip FROM trip")).one()
        assert tuple(trip) == ("not_bought", False)
        untimed = conn.execute(
            text("INSERT INTO trip_leg (trip_id, from_place, to_place) "
                 "VALUES (:t, 'b', 'c') RETURNING id"),
            {"t": trip_id},
        ).scalar()

    refused = run_alembic(scratch_database, "downgrade", previous("t5rip0000005"))
    assert refused.returncode != 0
    assert "will not invent a time" in refused.stderr

    # Mirror: without the untimed leg the same downgrade goes through.
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM trip_leg WHERE id = :id"), {"id": untimed})
    engine.dispose()
    migrate(scratch_database, "downgrade", previous("t5rip0000005"))
