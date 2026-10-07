"""The restore-tab registry: every table once, each after everything it points at."""

from app.database import Base
from app.services.sheet_backup.tabs import RESTORE_TABS


def test_every_table_has_exactly_one_restore_tab():
    tables = [tab.table.name for tab in RESTORE_TABS]
    assert sorted(tables) == sorted(Base.metadata.tables)
    assert len(set(tables)) == len(tables)


def test_each_tab_comes_after_every_table_its_foreign_keys_point_at():
    order = [tab.table.name for tab in RESTORE_TABS]
    for tab in RESTORE_TABS:
        for fk in tab.table.foreign_keys:
            target = fk.column.table.name
            assert order.index(target) < order.index(tab.table.name), (
                f"{tab.name} is restored before {target}, which it points at"
            )


def test_the_order_check_can_fail():
    """The mirror: trip_leg really does point at packing_list and trip, so the
    loop above has something to check - an FK-less registry would pass it."""
    leg = next(tab for tab in RESTORE_TABS if tab.table.name == "trip_leg")
    assert {fk.column.table.name for fk in leg.table.foreign_keys} == {"trip", "packing_list"}
