"""Backup into a fake spreadsheet, restore from it, and every refusal on the way.

The round trip is the test that matters, and its seed is load-bearing: every
table holds at least two rows, because an empty table round-trips trivially,
and the edge values - a booking code with a leading zero, a null count, an
irregular departure, an unlinked leg, an auto-saved row - are each a value a
careless format would change.
"""

from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy import select, text

from app.constants import Kind, Usage
from app.models import (
    LabelOption,
    PackingItem,
    PackingList,
    TransportDeparture,
    TransportOption,
    TransportRoute,
    Trip,
    TripLeg,
)
from app.routers.backup import get_sheet_client
from app.services.sheet_backup import client as sheet_client
from app.services.sheet_backup.backup import BACKUP_LOCK_KEY, NothingToBackUp, run_backup
from app.services.sheet_backup.client import SheetClient
from app.services.sheet_backup.format import CellRefused
from app.services.sheet_backup.restore import RestoreRefused, run_restore
from app.services.sheet_backup.tabs import BACKUP_INFO, RESTORE_TABS
from tests.fake_sheets import FakeSpreadsheet, api_error

TPE = timezone(timedelta(hours=8))
NOW = datetime(2026, 10, 7, 6, 30, tzinfo=timezone.utc)


@pytest.fixture
def fake():
    return FakeSpreadsheet()


@pytest.fixture
def sheets(fake):
    return SheetClient(fake)


@pytest.fixture
def seeded(db_session):
    """Every table, at least two rows, with the edge values the spec names."""
    db = db_session
    db.add_all([LabelOption(kind="category", value="重要", position=0),
                LabelOption(kind="ticket_type", value="電子", position=1)])
    going = PackingList(name="台北去彰化", kind=Kind.FREE, usage=Usage.IN_USE, leg="outbound",
                        pair_id="pair-1", notes="=SUM(A1)", departure_at=date(2026, 10, 3))
    past = PackingList(name="上次", kind=Kind.FREE, usage=Usage.PAST,
                       auto_saved_at=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc))
    template = PackingList(name="範本", kind=Kind.TEMPLATE, archive_note=" 空白 ")
    db.add_all([going, past, template])
    db.flush()
    db.add_all([
        PackingItem(list_id=going.id, name="錢包", category="重要", quantity=1,
                    quantity_packed=None, need="bring", needs_double_check=True, position=0),
        PackingItem(list_id=going.id, name="鑰匙", detail="家鑰匙", quantity=2, quantity_packed=0,
                    unit="把", status="packed", timing="day_of", position=1, notes="TRUE"),
        PackingItem(list_id=past.id, name="傘", status="no_need", position=0),
    ])
    route = TransportRoute(from_place="宿舍", to_place="彰化火車站", notes="走路也行", position=0)
    empty_route = TransportRoute(from_place="台北車站", to_place="家", position=1)
    db.add_all([route, empty_route])
    db.flush()
    bus = TransportOption(route_id=route.id, mode="公車 307", advance_ticket=False, price=15,
                          duration="40分", position=0)
    train = TransportOption(route_id=route.id, mode="火車", advance_ticket=True, position=1,
                            timetable_url="https://example.invalid/t")
    db.add_all([bus, train])
    db.flush()
    db.add_all([
        TransportDeparture(option_id=bus.id, day_type="weekday", time=time(6, 10)),
        TransportDeparture(option_id=bus.id, day_type="weekday", time=time(8, 15), irregular=True),
        TransportDeparture(option_id=bus.id, day_type="holiday", time=time(7, 5)),
    ])
    trip = Trip(name="彰化 ⇄ 台北", kind=Kind.FREE, usage=Usage.IN_USE, notes="中秋")
    old_trip = Trip(name="去年", kind=Kind.FREE, usage=Usage.PAST,
                    auto_saved_at=datetime(2026, 8, 1, tzinfo=timezone.utc))
    db.add_all([trip, old_trip])
    db.flush()
    db.add_all([
        TripLeg(trip_id=trip.id, from_place="台北車站", to_place="彰化火車站",
                departs_at=datetime(2026, 10, 3, 0, 30, tzinfo=TPE),
                arrives_at=datetime(2026, 10, 3, 3, 0, tzinfo=TPE),
                service="火車 - 自強", booking_code="0123", booked=True, paid=True,
                price=550, packing_list_id=going.id),
        TripLeg(trip_id=trip.id, from_place="彰化火車站", to_place="台北車站",  # unlinked
                departs_at=datetime(2026, 10, 5, 18, 6, tzinfo=TPE),
                arrives_at=datetime(2026, 10, 5, 20, 59, tzinfo=TPE)),
        TripLeg(trip_id=old_trip.id, from_place="甲", to_place="乙",
                departs_at=datetime(2025, 10, 5, 8, 0, tzinfo=TPE),
                arrives_at=datetime(2025, 10, 5, 9, 0, tzinfo=TPE)),
    ])
    db.commit()
    return db


def snapshot(db) -> dict[str, list[dict]]:
    db.expire_all()
    return {
        tab.table.name: [dict(row) for row in
                         db.execute(select(tab.table).order_by(tab.table.c.id)).mappings()]
        for tab in RESTORE_TABS
    }


def counts(db) -> dict[str, int]:
    return {name: len(rows) for name, rows in snapshot(db).items()}


def wipe(db, restart_at: dict[str, int]) -> None:
    """Empty every table, and move each sequence back to the lowest restored id.

    The sequences are what make the collision check bite: left where seeding
    put them, they are already past every restored id, and a restore that never
    reset them would pass. Moved back, the next insert lands on a restored id
    unless the restore moved them forward again.
    """
    for tab in reversed(RESTORE_TABS):
        db.execute(tab.table.delete())
        seq = db.scalar(text("SELECT pg_get_serial_sequence(:t, 'id')"), {"t": tab.table.name})
        db.execute(text(f"ALTER SEQUENCE {seq} RESTART WITH {restart_at[tab.table.name]}"))
    db.commit()


# --- the round trip ------------------------------------------------------------


def test_a_backup_restores_every_column_of_every_row(seeded, fake, sheets):
    before = snapshot(seeded)
    assert all(len(rows) >= 2 for rows in before.values()), "every table must be seeded"

    run_backup(seeded, sheets, now=NOW)
    assert fake.tab("Trip Leg").values()[1][list(TripLeg.__table__.c.keys()).index("booking_code")] == "0123"

    wipe(seeded, {name: rows[0]["id"] for name, rows in before.items()})
    assert not any(counts(seeded).values())

    result = run_restore(seeded, sheets)
    assert result.rows == {name: len(rows) for name, rows in before.items()}
    assert snapshot(seeded) == before


def test_after_a_restore_new_rows_take_fresh_ids(seeded, sheets):
    before = snapshot(seeded)
    run_backup(seeded, sheets, now=NOW)
    wipe(seeded, {name: rows[0]["id"] for name, rows in before.items()})
    run_restore(seeded, sheets)

    top = {name: max(row["id"] for row in rows) for name, rows in before.items()}
    a_list, a_route, a_trip = (before[t][0]["id"] for t in ("packing_list", "transport_route", "trip"))
    an_option = before["transport_option"][0]["id"]
    new = {
        "label_option": LabelOption(kind="bag", value="背包"),
        "packing_list": PackingList(name="新"),
        "packing_item": PackingItem(list_id=a_list, name="新"),
        "transport_route": TransportRoute(from_place="a", to_place="b"),
        "transport_option": TransportOption(route_id=a_route, mode="新"),
        "transport_departure": TransportDeparture(option_id=an_option, day_type="holiday",
                                                  time=time(23, 59)),
        "trip": Trip(name="新"),
        "trip_leg": TripLeg(trip_id=a_trip, from_place="a", to_place="b",
                            departs_at=NOW, arrives_at=NOW + timedelta(hours=1)),
    }
    seeded.add_all(new.values())
    seeded.commit()
    assert {name: row.id for name, row in new.items()} == {name: n + 1 for name, n in top.items()}


# --- restore refusals ------------------------------------------------------------


def test_a_restore_from_another_revision_is_refused_and_writes_nothing(seeded, fake, sheets):
    run_backup(seeded, sheets, now=NOW)
    info = fake.tab(BACKUP_INFO)
    row = next(r for (r, c), v in info.cells.items() if v == "alembic_revision")
    info.cells[(row, 2)] = "some_other_rev"
    seeded.execute(text("UPDATE trip SET name = 'changed since'"))
    seeded.commit()

    # --replace, so the non-empty refusal cannot be the one that fires.
    with pytest.raises(RestoreRefused, match="some_other_rev"):
        run_restore(seeded, sheets, replace=True)
    assert {t.name for t in seeded.scalars(select(Trip))} == {"changed since"}


def test_a_restore_into_a_database_with_rows_needs_replace(seeded, sheets):
    run_backup(seeded, sheets, now=NOW)
    before = counts(seeded)
    seeded.execute(text("UPDATE trip SET name = 'changed since'"))
    seeded.commit()

    with pytest.raises(RestoreRefused) as refused:
        run_restore(seeded, sheets)
    assert refused.value.counts == before
    assert {t.name for t in seeded.scalars(select(Trip))} == {"changed since"}


def test_with_replace_the_same_database_is_restored(seeded, sheets):
    """The mirror: the same rows, the same sheet, and --replace."""
    run_backup(seeded, sheets, now=NOW)
    before = snapshot(seeded)
    seeded.execute(text("UPDATE trip SET name = 'changed since'"))
    seeded.add(LabelOption(kind="bag", value="added since"))
    seeded.commit()

    result = run_restore(seeded, sheets, replace=True)
    assert result.replaced["label_option"] == 3
    assert snapshot(seeded) == before


def test_a_dry_run_restores_nothing(seeded, sheets):
    run_backup(seeded, sheets, now=NOW)
    seeded.execute(text("UPDATE trip SET name = 'changed since'"))
    seeded.commit()

    result = run_restore(seeded, sheets, replace=True, dry_run=True)
    assert result.dry_run and result.rows["trip"] == 2
    assert {t.name for t in seeded.scalars(select(Trip))} == {"changed since"}


def test_a_missing_restore_tab_is_refused(seeded, fake, sheets):
    run_backup(seeded, sheets, now=NOW)
    fake.tabs.remove(fake.tab("Trip Leg"))
    with pytest.raises(RestoreRefused, match="Trip Leg"):
        run_restore(seeded, sheets, replace=True)
    assert counts(seeded)["trip_leg"] == 3


def test_a_bad_cell_is_refused_naming_tab_row_and_column(seeded, fake, sheets):
    run_backup(seeded, sheets, now=NOW)
    seeded.execute(text("UPDATE trip SET name = 'changed since'"))
    seeded.commit()
    item = fake.tab("Packing Item")
    column = list(PackingItem.__table__.c.keys()).index("quantity") + 1
    item.cells[(3, column)] = "lots"

    with pytest.raises(CellRefused, match="Packing Item, row 3, column quantity"):
        run_restore(seeded, sheets, replace=True)
    assert {t.name for t in seeded.scalars(select(Trip))} == {"changed since"}


def test_an_insert_that_fails_halfway_rolls_back_the_deletes_too(seeded, fake, sheets):
    """Parsing passes; the database refuses the last tab. By then every table
    has been emptied and the earlier tabs inserted - all of it must go back."""
    run_backup(seeded, sheets, now=NOW)
    before = snapshot(seeded)
    seeded.execute(text("UPDATE trip SET name = 'changed since'"))
    seeded.commit()
    leg = fake.tab("Trip Leg")
    column = list(TripLeg.__table__.c.keys()).index("trip_id") + 1
    leg.cells[(2, column)] = "999999"  # no such trip

    with pytest.raises(Exception, match="fk_trip_leg_trip"):
        run_restore(seeded, sheets, replace=True)
    assert counts(seeded) == {name: len(rows) for name, rows in before.items()}
    assert {t.name for t in seeded.scalars(select(Trip))} == {"changed since"}


def test_an_unknown_header_is_refused(seeded, fake, sheets):
    run_backup(seeded, sheets, now=NOW)
    fake.tab("Trip").cells[(1, 30)] = "colour"
    with pytest.raises(CellRefused, match="Trip, row 1, column colour"):
        run_restore(seeded, sheets, replace=True)


def test_a_missing_non_null_column_is_refused(seeded, fake, sheets):
    run_backup(seeded, sheets, now=NOW)
    route = fake.tab("Transport Route")
    column = list(TransportRoute.__table__.c.keys()).index("from_place") + 1
    route.cells = {(r, c): v for (r, c), v in route.cells.items() if c != column}
    with pytest.raises(CellRefused, match="Transport Route, row 1, column from_place"):
        run_restore(seeded, sheets, replace=True)


# --- backup refusals ------------------------------------------------------------


def test_an_all_empty_database_is_refused_before_anything_is_written(db_session, fake, sheets):
    # Load-bearing: the sheet holds a previous backup, which is what an
    # all-empty run would destroy.
    fake.add_tab("Trip", [["id", "name"], ["1", "keep me"]])
    with pytest.raises(NothingToBackUp):
        run_backup(db_session, sheets, now=NOW)
    assert fake.calls == []
    assert fake.tab("Trip").values() == [["id", "name"], ["1", "keep me"]]


def test_one_row_anywhere_is_enough_to_back_up(db_session, fake, sheets):
    """The mirror: the same empty sheet, one label option, and it runs."""
    db_session.add(LabelOption(kind="bag", value="背包"))
    db_session.commit()
    result = run_backup(db_session, sheets, now=NOW)
    assert result.rows["label_option"] == 1


def test_one_empty_table_among_full_ones_backs_up_as_a_header_only_tab(seeded, fake, sheets):
    # Load-bearing: the previous backup holds routes, so the trim has rows to
    # remove; every other table still has rows, so this is not the all-empty
    # refusal. The last route deleted is an ordinary state, not a wrong database.
    run_backup(seeded, sheets, now=NOW)
    assert len(fake.tab("Transport Route").values()) == 3
    seeded.execute(text("DELETE FROM transport_route"))
    seeded.commit()

    result = run_backup(seeded, sheets, now=NOW)
    assert result.rows["transport_route"] == 0
    assert fake.tab("Transport Route").values() == [list(TransportRoute.__table__.c.keys())]
    assert len(fake.tab("Trip Leg").values()) == 4


# --- the readable tabs ------------------------------------------------------------


def test_the_readable_set_follows_the_dashboard_and_the_trips_legs(db_session, fake, sheets):
    db = db_session
    in_use = PackingList(name="使用中清單", usage=Usage.IN_USE)
    upcoming = PackingList(name="未來清單", usage=Usage.UPCOMING)
    linked = PackingList(name="回程清單", usage=Usage.UNUSED)  # only the leg brings it in
    saved = PackingList(name="保存清單", kind=Kind.SAVED)
    unused = PackingList(name="閒置清單", usage=Usage.UNUSED)
    trip = Trip(name="這次", usage=Usage.IN_USE)
    saved_trip = Trip(name="保存行程", kind=Kind.SAVED)
    db.add_all([in_use, upcoming, linked, saved, unused, trip, saved_trip])
    db.flush()
    db.add(TripLeg(trip_id=trip.id, from_place="a", to_place="b", packing_list_id=linked.id,
                   departs_at=NOW, arrives_at=NOW + timedelta(hours=1)))
    db.commit()

    fake.add_tab("My notes", [["mine"]])
    fake.add_tab("清單 · 舊的", [["old"]])
    fake.add_tab("行程 · 舊的", [["old"]])

    run_backup(db, sheets, now=NOW)

    titles = fake.titles()
    assert titles[:5] == ["總覽", "清單 · 使用中清單", "清單 · 未來清單", "清單 · 回程清單", "行程 · 這次"]
    assert titles[5:7] == ["交通", BACKUP_INFO]
    assert "清單 · 保存清單" not in titles and "清單 · 閒置清單" not in titles
    assert "行程 · 保存行程" not in titles
    assert "清單 · 舊的" not in titles and "行程 · 舊的" not in titles
    assert titles[-1] == "My notes"
    assert fake.tab("My notes").values() == [["mine"]]

    overview = fake.tab("總覽").values()
    gid = fake.tab("清單 · 回程清單").id
    assert any(f'#gid={gid}"' in cell for row in overview for cell in row)


def test_a_list_tab_reads_in_the_sheets_own_words(seeded, fake, sheets):
    run_backup(seeded, sheets, now=NOW)
    rows = fake.tab("清單 · 台北去彰化").values()
    assert rows[0] == ["台北去彰化"]
    assert ["狀態", "使用中"] in rows
    assert ["出發", "2026-10-03"] in rows  # the leg's Taipei date, 00:30 local
    assert ["去程/回程", "去程"] in rows
    assert ["已處理", "1 / 2"] in rows
    wallet = next(r for r in rows if len(r) > 1 and r[1] == "錢包")
    assert wallet[3] == "需帶" and wallet[5] == "" and wallet[9] == "未確認"


def test_a_trip_tab_shows_taipei_times_and_the_linked_list(seeded, fake, sheets):
    run_backup(seeded, sheets, now=NOW)
    rows = fake.tab("行程 · 彰化 ⇄ 台北").values()
    first = next(r for r in rows if r and r[0] == "台北車站")
    assert first[2] == "2026-10-03 00:30"
    assert first[12] == "0123"
    assert first[14] == "台北去彰化"


def test_the_transport_tab_marks_irregular_departures(seeded, fake, sheets):
    run_backup(seeded, sheets, now=NOW)
    rows = fake.tab("交通").values()
    bus = next(r for r in rows if len(r) > 2 and r[2] == "公車 307")
    assert bus[12] == "06:10 *08:15"
    assert bus[13] == "07:05"
    assert any(r[:2] == ["台北車站", "家"] for r in rows)  # a route with no options


# --- the endpoint -----------------------------------------------------------------


@pytest.fixture
def api(client, sheets):
    from app.main import app

    app.dependency_overrides[get_sheet_client] = lambda: sheets
    return client


def test_post_backup_answers_tabs_rows_and_time(api, seeded):
    response = api.post("/api/backup")
    assert response.status_code == 200
    body = response.json()
    assert body["rows"]["trip_leg"] == 3
    assert body["tabs"] >= 12
    assert datetime.fromisoformat(body["backed_up_at"]).tzinfo is not None


def test_a_held_lock_is_a_409_and_writes_nothing(api, seeded, fake, engine):
    # Load-bearing: the database has rows and the sheet is reachable, so
    # without the lock this backup would succeed (the mirror above).
    holder = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        assert holder.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": BACKUP_LOCK_KEY}).scalar()
        response = api.post("/api/backup")
    finally:
        holder.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": BACKUP_LOCK_KEY})
        holder.close()
    assert response.status_code == 409
    assert fake.calls == []


def test_an_empty_database_is_a_422(api, fake):
    fake.add_tab("Trip", [["id"], ["1"]])
    assert api.post("/api/backup").status_code == 422
    assert fake.tab("Trip").values() == [["id"], ["1"]]


def test_sheets_unavailable_is_a_503(api, seeded, fake, monkeypatch):
    monkeypatch.setattr(sheet_client.time, "sleep", lambda seconds: None)
    fake.failures["values_batch_update"] = api_error(503)
    response = api.post("/api/backup")
    assert response.status_code == 503
    assert fake.calls.count("values_batch_update") == 3


def test_sheets_not_configured_is_a_503(client, seeded, monkeypatch):
    monkeypatch.setattr(sheet_client.settings, "google_credentials_json", None)
    response = client.post("/api/backup")
    assert response.status_code == 503
    assert "GOOGLE_CREDENTIALS_JSON" in response.json()["detail"]
