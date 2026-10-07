"""Which lists and trips are current: the dashboard's rule, and the sheet's.

`onDashboard` in `frontend/src/lib/kinds.js` is the rule the screens use, and
the sheet backup needs the same answer for its readable tabs. It is written
again here rather than served, because the backup runs with no browser - the
nightly timer is a shell. Two copies of a rule drift, so
`tests/unit/test_dashboard_rule.py` pins this one to the cases `kinds.test.js`
pins the other to: changing either without the other turns a test red.
"""

from collections.abc import Iterable, Sequence
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.constants import Kind, Usage
from app.models import PackingList, Trip, TripLeg

Row = TypeVar("Row")

#: 使用中 before 未來使用: the order the dashboard shows them in.
CURRENT = (Usage.IN_USE, Usage.UPCOMING)


def on_dashboard(rows: Iterable[Row]) -> list[Row]:
    """一般 rows that are 使用中 or 未來使用, 使用中 first, order otherwise kept."""
    current = [row for row in rows if row.kind == Kind.FREE and row.usage in CURRENT]
    return [row for usage in CURRENT for row in current if row.usage == usage]


def readable_set(db: Session) -> tuple[list[PackingList], list[Trip]]:
    """The lists and trips the sheet gets a readable tab for, in tab order.

    Trips are the dashboard's. Lists are the dashboard's **plus** every list
    linked from a leg of one of those trips, whatever its own kind or usage:
    a trip in use whose return list nobody has marked 使用中 yet is exactly the
    case where the app dies mid-trip and the sheet is all there is.

    The rows start in the index endpoints' order - newest created first, then
    highest id - so a tab sits where the screen would put it. The linked extras
    follow the dashboard lists, trip by trip in that same order and leg by leg
    in departure order.
    """
    lists = db.scalars(
        select(PackingList)
        .options(selectinload(PackingList.items), selectinload(PackingList.trip_leg))
        .order_by(PackingList.created_at.desc(), PackingList.id.desc())
    ).all()
    trips = on_dashboard(
        db.scalars(
            select(Trip)
            .options(selectinload(Trip.legs).selectinload(TripLeg.packing_list))
            .order_by(Trip.created_at.desc(), Trip.id.desc())
        ).all()
    )
    return _with_linked(on_dashboard(lists), trips), trips


def _with_linked(lists: Sequence[PackingList], trips: Sequence[Trip]) -> list[PackingList]:
    chosen = list(lists)
    seen = {row.id for row in chosen}
    for trip in trips:
        for leg in trip.legs:
            if leg.packing_list is not None and leg.packing_list.id not in seen:
                seen.add(leg.packing_list.id)
                chosen.append(leg.packing_list)
    return chosen
