"""`on_dashboard` is `onDashboard` in kinds.js, written twice; these pin them together.

The cases are kinds.test.js's own: the same filter (一般, 使用中 or 未來使用)
and the same order (soonest start first, no start last, ties in the order the
rows came in). Change the rule in one place and not the other, and one of the
two suites goes red.

The Python rule takes each row's start from `start_of` - a trip's earliest
departure, a list's effective date at Taipei 00:00 - so the cases here hand
it a `start` attribute instead; `start_of` itself is pinned below.
"""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from app.constants import TAIPEI
from app.models import PackingList, Trip, TripLeg
from app.services.domain.dashboard import on_dashboard, start_of


def row(id, kind="free", usage=None, start=None):
    if usage is None and kind == "free":
        usage = "unused"
    return SimpleNamespace(id=id, kind=kind, usage=usage, start=start)


def by_start(rows):
    return [r.id for r in on_dashboard(rows, start=lambda r: r.start)]


T = datetime(2026, 11, 4, 9, 0, tzinfo=TAIPEI)


def test_keeps_in_use_and_upcoming_free_rows_order_kept_without_starts():
    rows = [row(1, "free", "upcoming"), row(2, "free", "unused"), row(3, "free", "in_use"),
            row(4, "free", "past"), row(5, "saved"), row(6, "free", "upcoming"),
            row(7, "free", "in_use")]
    # No row has a start, so every one ties and the incoming order stands:
    # 使用中 no longer goes first.
    assert by_start(rows) == [1, 3, 6, 7]


def test_soonest_start_first_and_no_start_last():
    rows = [row(1, "free", "in_use"), row(2, "free", "upcoming", T + timedelta(days=2)),
            row(3, "free", "in_use", T), row(4, "free", "upcoming"),
            row(5, "free", "upcoming", T + timedelta(hours=1))]
    assert by_start(rows) == [3, 5, 2, 1, 4]


def test_equal_starts_keep_the_incoming_order():
    rows = [row(1, "free", "upcoming", T), row(2, "free", "in_use", T)]
    assert by_start(rows) == [1, 2]


def test_a_template_or_saved_row_is_never_current():
    assert on_dashboard([row(1, "template"), row(2, "saved")], start=lambda r: r.start) == []


# --- start_of -------------------------------------------------------------------


def leg(departs):
    return TripLeg(from_place="a", to_place="b", departs_at=departs, arrives_at=departs)


def test_a_trips_start_is_its_earliest_timed_entry():
    trip = Trip(name="t", legs=[leg(T + timedelta(days=1)), leg(None), leg(T)])
    assert start_of(trip) == T
    assert start_of(Trip(name="untimed", legs=[leg(None)])) is None


def test_a_lists_start_is_its_effective_date_at_taipei_midnight():
    lst = PackingList(name="l", departure_at=date(2026, 11, 4))
    assert start_of(lst) == datetime(2026, 11, 4, tzinfo=TAIPEI)
    # 2026-11-03 17:00 UTC is already 11-04 in Taipei: the linked leg's Taipei day.
    linked = PackingList(name="l", departure_at=date(2026, 1, 1))
    linked.trip_leg = leg(datetime(2026, 11, 3, 17, 0, tzinfo=timezone.utc))
    assert start_of(linked) == datetime(2026, 11, 4, tzinfo=TAIPEI)
    assert start_of(PackingList(name="none")) is None
