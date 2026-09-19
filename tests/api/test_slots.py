"""The cap, and the fixture that makes it possible to break.

**A cap asserted against an empty database passes because there was nothing to
evict** — green on day one, green through the change that breaks it, green
forever. `three_working_lists` is not scene setting; it is the only reason any
refusal here can fail, and every test that asserts a limit bites uses it. The
mirror cases use the same fixture, so a green proves the rule did the refusing
rather than an empty table doing it for free.

`created_at` is set explicitly rather than left to the default. `now()` is the
transaction's start time in PostgreSQL and these tests run inside one
transaction, so every row would otherwise share a timestamp and "the oldest"
would mean nothing.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models import PackingItem, PackingList
from app.services.domain.packing import (
    SLOT_CAP,
    copy_items,
    count_slots,
    evict,
    oldest_slot,
)

EPOCH = datetime(2026, 9, 1, tzinfo=timezone.utc)


def make_list(db_session, name, *, days=0, **overrides) -> PackingList:
    packing_list = PackingList(
        name=name, created_at=EPOCH + timedelta(days=days), **overrides
    )
    db_session.add(packing_list)
    db_session.flush()
    return packing_list


@pytest.fixture
def three_working_lists(db_session):
    """Three lists, neither saved nor templates, oldest first.

    Load-bearing, and it looks like decoration. Without it every assertion
    below about a limit being reached is vacuously true.
    """
    return [
        make_list(db_session, "Kyoto", days=0),
        make_list(db_session, "Seoul", days=1),
        make_list(db_session, "Taipei", days=2),
    ]


def test_three_working_lists_fill_the_cap(three_working_lists, db_session):
    assert count_slots(db_session) == SLOT_CAP


def test_two_working_lists_do_not_fill_the_cap(three_working_lists, db_session):
    # The mirror. Same fixture, one list removed: the count must actually move,
    # which is what proves the count above was counting and not just returning
    # a constant.
    db_session.delete(three_working_lists[-1])
    db_session.flush()
    assert count_slots(db_session) == SLOT_CAP - 1


def test_an_empty_database_has_no_slots(db_session):
    # Stated so the vacuous case is visible rather than implied. Every refusal
    # test above needs the fixture precisely because this is what a fresh
    # database looks like.
    assert count_slots(db_session) == 0


def test_a_round_trip_pair_counts_as_one_slot(db_session):
    make_list(db_session, "Osaka out", days=0, pair_id="osaka", leg="outbound")
    make_list(db_session, "Osaka back", days=0, pair_id="osaka", leg="return")
    assert count_slots(db_session) == 1


def test_three_round_trips_still_fit(db_session):
    for index, trip in enumerate(("osaka", "hanoi", "lisbon")):
        make_list(db_session, f"{trip} out", days=index, pair_id=trip, leg="outbound")
        make_list(db_session, f"{trip} back", days=index, pair_id=trip, leg="return")
    assert count_slots(db_session) == SLOT_CAP


def test_saved_and_template_lists_do_not_count(three_working_lists, db_session):
    # Five rows in the table, three slots. Both exemptions are asserted here
    # because they are independent flags and one could work while the other
    # does not.
    make_list(db_session, "kept", days=3, saved=True)
    make_list(db_session, "starting point", days=4, template=True)
    assert count_slots(db_session) == SLOT_CAP


def test_a_list_that_is_both_saved_and_a_template_still_does_not_count(
    three_working_lists, db_session
):
    make_list(db_session, "both", days=3, saved=True, template=True)
    assert count_slots(db_session) == SLOT_CAP


def test_the_oldest_slot_is_the_one_that_would_go(three_working_lists, db_session):
    slot = oldest_slot(db_session)
    assert [packing_list.name for packing_list in slot] == ["Kyoto"]


def test_the_oldest_slot_skips_saved_lists(three_working_lists, db_session):
    # An older list that has been saved must not be offered up. Saving is how
    # you rescue something from the cap, so a saved list being evicted anyway
    # would make the rescue meaningless.
    make_list(db_session, "ancient", days=-10, saved=True)
    slot = oldest_slot(db_session)
    assert [packing_list.name for packing_list in slot] == ["Kyoto"]


def test_the_oldest_slot_is_a_whole_pair(db_session):
    make_list(db_session, "Osaka out", days=0, pair_id="osaka", leg="outbound")
    make_list(db_session, "Osaka back", days=0, pair_id="osaka", leg="return")
    make_list(db_session, "Seoul", days=5)

    slot = oldest_slot(db_session)
    assert sorted(packing_list.name for packing_list in slot) == [
        "Osaka back",
        "Osaka out",
    ]


def test_an_empty_database_offers_nothing_to_evict(db_session):
    assert oldest_slot(db_session) == []


def test_evicting_a_pair_deletes_both_lists_and_their_items(db_session):
    outbound = make_list(db_session, "Osaka out", days=0, pair_id="osaka", leg="outbound")
    inbound = make_list(db_session, "Osaka back", days=0, pair_id="osaka", leg="return")
    db_session.add(PackingItem(list_id=outbound.id, name="passport"))
    db_session.add(PackingItem(list_id=inbound.id, name="souvenirs"))
    db_session.flush()

    evict(db_session, oldest_slot(db_session))

    assert db_session.query(PackingList).count() == 0
    # Cascade, not a second delete in the service: leaving orphaned items would
    # look like nothing at all until something counted rows.
    assert db_session.query(PackingItem).count() == 0


def test_evicting_leaves_every_other_slot_alone(three_working_lists, db_session):
    evict(db_session, oldest_slot(db_session))
    remaining = sorted(
        packing_list.name for packing_list in db_session.query(PackingList).all()
    )
    assert remaining == ["Seoul", "Taipei"]


def test_a_copy_carries_the_definition_and_resets_the_state(db_session):
    source = make_list(db_session, "template", template=True)
    db_session.add(
        PackingItem(
            list_id=source.id,
            name="socks",
            category="clothes",
            bag="checked",
            quantity=5,
            unit="pairs",
            timing="night_before",
            needs_double_check=True,
            notes="the warm ones",
            position=3,
            # State from the last trip. None of this may survive the copy.
            status="packed",
            quantity_packed=5,
            double_checked=True,
        )
    )
    db_session.flush()

    target = make_list(db_session, "Sapporo", days=1)
    copy_items(db_session, source, target)

    copied = db_session.query(PackingItem).filter_by(list_id=target.id).one()
    # Field by field, because a copy that silently drops one column is a list
    # missing an item and nothing says so.
    assert copied.name == "socks"
    assert copied.category == "clothes"
    assert copied.bag == "checked"
    assert copied.quantity == 5
    assert copied.unit == "pairs"
    assert copied.timing == "night_before"
    assert copied.needs_double_check is True
    assert copied.notes == "the warm ones"
    assert copied.position == 3

    assert copied.status == "not_packed"
    assert copied.quantity_packed == 0
    assert copied.double_checked is False


def test_a_copy_leaves_the_source_untouched(db_session):
    source = make_list(db_session, "template", template=True)
    db_session.add(
        PackingItem(list_id=source.id, name="socks", status="packed", quantity_packed=2)
    )
    db_session.flush()

    target = make_list(db_session, "Sapporo", days=1)
    copy_items(db_session, source, target)

    original = db_session.query(PackingItem).filter_by(list_id=source.id).one()
    assert original.status == "packed"
    assert original.quantity_packed == 2


def test_copying_an_empty_list_is_not_an_error(db_session):
    source = make_list(db_session, "empty template", template=True)
    target = make_list(db_session, "Sapporo", days=1)
    copy_items(db_session, source, target)
    assert db_session.query(PackingItem).filter_by(list_id=target.id).count() == 0
