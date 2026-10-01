from datetime import date

import pytest

from app.models import PackingList, TransportRoute, Trip
from app.services.sheet_import.parse import parse_workbook
from app.services.sheet_import.write import ImportClash, find_clashes, write_sheet
from tests.sheet_fixture import workbook


@pytest.fixture
def sheet():
    return parse_workbook(workbook(), trip_start=date(2026, 9, 24), trip_name="彰化 ⇄ 台北")


def test_an_import_writes_lists_routes_and_the_trip(db_session, sheet):
    write_sheet(db_session, sheet)
    db_session.commit()
    names = sorted(row.name for row in db_session.query(PackingList))
    assert names == ["台北去彰化", "彰化回台北"]
    assert db_session.query(TransportRoute).count() == 3
    trip = db_session.query(Trip).one()
    assert [leg.packing_list.name for leg in trip.legs] == ["彰化回台北", "台北去彰化"]


def test_an_import_remembers_labels(client, db_session, sheet):
    write_sheet(db_session, sheet)
    db_session.commit()
    kinds = {row["kind"] for row in client.get("/api/label-options").json()}
    assert {"category", "location", "ticket_type"} <= kinds


def test_an_import_refuses_when_any_target_exists_and_writes_nothing(db_session, sheet):
    # Load-bearing: one pre-existing route is the only clash, so the refusal
    # has to come from the route check and not from an empty table.
    db_session.add(TransportRoute(from_place="宿舍", to_place="彰化火車站"))
    db_session.commit()
    with pytest.raises(ImportClash) as refused:
        write_sheet(db_session, sheet)
    assert any("宿舍" in line for line in refused.value.clashes)
    assert db_session.query(PackingList).count() == 0
    assert db_session.query(Trip).count() == 0


def test_an_import_into_an_empty_database_has_no_clashes(db_session, sheet):
    assert find_clashes(db_session, sheet) == []
