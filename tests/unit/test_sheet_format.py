"""A value to a cell and back, by column type, and the cells that are refused."""

from datetime import date, datetime, time, timedelta, timezone

import pytest

from app.models import PackingItem, PackingList, TransportDeparture, TripLeg
from app.services.sheet_backup.format import from_sheet, to_sheet

TPE = timezone(timedelta(hours=8))
C = {
    "booking_code": TripLeg.__table__.c.booking_code,
    "departs_at": TripLeg.__table__.c.departs_at,
    "booked": TripLeg.__table__.c.booked,
    "quantity": PackingItem.__table__.c.quantity,
    "departure_at": PackingList.__table__.c.departure_at,
    "time": TransportDeparture.__table__.c.time,
    "notes": PackingItem.__table__.c.notes,
}


@pytest.mark.parametrize(("column", "value", "cell"), [
    ("booking_code", "0123", "0123"),
    ("departs_at", datetime(2026, 9, 24, 18, 6, tzinfo=TPE), "2026-09-24T18:06:00+08:00"),
    ("booked", True, "TRUE"),
    ("booked", False, "FALSE"),
    ("quantity", 0, "0"),
    ("quantity", None, ""),
    ("departure_at", date(2026, 10, 3), "2026-10-03"),
    ("time", time(6, 10), "06:10:00"),
    ("notes", " padded =SUM(A1) ", " padded =SUM(A1) "),
])
def test_a_value_survives_the_cell(column, value, cell):
    assert to_sheet(value) == cell
    assert from_sheet(C[column], cell) == value


def test_a_timestamp_keeps_the_instant_whatever_offset_it_is_written_in():
    utc = datetime(2026, 9, 24, 10, 6, tzinfo=timezone.utc)
    assert from_sheet(C["departs_at"], to_sheet(utc)) == datetime(2026, 9, 24, 18, 6, tzinfo=TPE)


@pytest.mark.parametrize(("column", "cell"), [
    ("quantity", "lots"),
    ("quantity", "1.5"),
    ("booked", "yes"),
    ("departs_at", "2026-09-24T18:06:00"),  # no offset: which 18:06?
    ("departure_at", "10/03"),
    ("time", "6 am"),
])
def test_an_unreadable_cell_is_refused_not_nulled(column, cell):
    with pytest.raises(ValueError):
        from_sheet(C[column], cell)
