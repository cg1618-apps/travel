"""What a copy carries, and what it resets."""

from datetime import datetime, timedelta, timezone

from app.constants import Kind
from app.models import PackingItem, PackingList
from app.services.domain.packing import copy_items

EPOCH = datetime(2026, 9, 1, tzinfo=timezone.utc)


def make_list(db_session, name, *, days=0, **overrides) -> PackingList:
    packing_list = PackingList(
        name=name, created_at=EPOCH + timedelta(days=days), **overrides
    )
    db_session.add(packing_list)
    db_session.flush()
    return packing_list


def test_a_copy_carries_the_definition_and_resets_the_state(db_session):
    source = make_list(db_session, "template", kind=Kind.TEMPLATE)
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
    source = make_list(db_session, "template", kind=Kind.TEMPLATE)
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
    source = make_list(db_session, "empty template", kind=Kind.TEMPLATE)
    target = make_list(db_session, "Sapporo", days=1)
    copy_items(db_session, source, target)
    assert db_session.query(PackingItem).filter_by(list_id=target.id).count() == 0
