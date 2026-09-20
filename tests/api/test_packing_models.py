"""What the schema itself refuses, and what it cleans up.

These are database-level guarantees asserted at the database level. A
CheckConstraint that exists only in the model is a constraint the migration
forgot, and every read path in the application would still look correct — the
fixture runs the migrations precisely so that these tests are asking the
shipped schema and not the ORM's opinion of it.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.constants import LabelKind, Status, Timing, Visibility
from app.models import LabelOption, PackingItem, PackingList


def a_list(**overrides) -> PackingList:
    return PackingList(name=overrides.pop("name", "Tokyo"), **overrides)


def test_a_list_defaults_to_a_working_private_list(db_session):
    packing_list = a_list()
    db_session.add(packing_list)
    db_session.flush()

    assert packing_list.saved is False
    assert packing_list.template is False
    assert packing_list.visibility == Visibility.PRIVATE
    assert packing_list.departure_at is None
    assert packing_list.pair_id is None


def test_an_unknown_status_is_refused_by_the_database(db_session):
    packing_list = a_list()
    db_session.add(packing_list)
    db_session.flush()

    db_session.add(PackingItem(list_id=packing_list.id, name="passport", status="half"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_an_unknown_timing_is_refused_by_the_database(db_session):
    packing_list = a_list()
    db_session.add(packing_list)
    db_session.flush()

    db_session.add(
        PackingItem(list_id=packing_list.id, name="charger", timing="eventually")
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_every_declared_status_and_timing_is_actually_accepted(db_session):
    # The mirror of the two refusals above. Without it, a constraint that
    # refused EVERYTHING would pass both of them - the tests would be green and
    # the application unusable.
    packing_list = a_list()
    db_session.add(packing_list)
    db_session.flush()

    for status in Status:
        for timing in Timing:
            db_session.add(
                PackingItem(
                    list_id=packing_list.id,
                    name=f"{status}-{timing}",
                    status=status,
                    timing=timing,
                )
            )
    db_session.flush()


def test_an_unknown_leg_is_refused_but_no_leg_is_allowed(db_session):
    # `leg` is nullable AND constrained, which is the combination easiest to
    # get wrong: `leg IN (...)` is NULL rather than TRUE for a NULL column, so
    # a constraint written without the IS NULL arm still passes - and one
    # written as a plain IN would too. Both arms are asserted.
    db_session.add(a_list(leg=None))
    db_session.flush()

    db_session.add(a_list(name="Osaka", leg="sideways"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_an_unknown_visibility_is_refused_by_the_database(db_session):
    # Nothing reads visibility yet. The constraint is what stops an unreviewed
    # value existing on the day the sharing checks start reading it.
    db_session.add(a_list(visibility="everyone"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_deleting_a_list_takes_its_items_with_it(db_session):
    # ON DELETE CASCADE in the database, not only cascade= on the relationship.
    # Eviction deletes through the ORM, but a DELETE run by hand from psql must
    # not leave orphans either - so this deletes with raw SQL, which bypasses
    # the ORM cascade entirely and asks the schema the question.
    packing_list = a_list()
    db_session.add(packing_list)
    db_session.flush()
    db_session.add(PackingItem(list_id=packing_list.id, name="toothbrush"))
    db_session.flush()

    db_session.execute(
        text("DELETE FROM packing_list WHERE id = :id"), {"id": packing_list.id}
    )

    remaining = db_session.execute(text("SELECT count(*) FROM packing_item")).scalar()
    assert remaining == 0


def test_an_item_defaults_to_unpacked_unverified_and_uncounted(db_session):
    packing_list = a_list()
    db_session.add(packing_list)
    db_session.flush()

    item = PackingItem(list_id=packing_list.id, name="socks")
    db_session.add(item)
    db_session.flush()

    assert item.status == Status.NOT_PACKED
    assert item.timing == Timing.WHENEVER
    assert item.quantity is None
    assert item.quantity_packed == 0
    assert item.needs_double_check is False
    assert item.double_checked is False


def test_a_quantity_may_be_null_while_the_packed_count_is_not(db_session):
    # "How many" does not apply to a hairbrush. The count still has to be a
    # number, because the screen renders it.
    packing_list = a_list()
    db_session.add(packing_list)
    db_session.flush()

    item = PackingItem(list_id=packing_list.id, name="hairbrush", quantity=None)
    db_session.add(item)
    db_session.flush()
    assert item.quantity_packed == 0


def test_an_item_may_be_packed_beyond_its_target(db_session):
    # Over-packing is not an error and no constraint forbids it. Pinned here so
    # nobody adds a well-meaning CHECK that makes the app refuse a real state.
    packing_list = a_list()
    db_session.add(packing_list)
    db_session.flush()

    item = PackingItem(
        list_id=packing_list.id, name="socks", quantity=3, quantity_packed=5
    )
    db_session.add(item)
    db_session.flush()
    assert item.quantity_packed == 5


def test_the_same_option_value_cannot_be_recorded_twice_for_one_kind(db_session):
    db_session.add(LabelOption(kind=LabelKind.CATEGORY, value="clothes"))
    db_session.flush()
    db_session.add(LabelOption(kind=LabelKind.CATEGORY, value="clothes"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_the_same_value_may_exist_for_a_different_kind(db_session):
    # The unique constraint is on the pair. "day bag" is a plausible category
    # and a plausible bag, and they are different facts.
    db_session.add(LabelOption(kind=LabelKind.CATEGORY, value="day bag"))
    db_session.add(LabelOption(kind=LabelKind.BAG, value="day bag"))
    db_session.flush()


def test_an_unknown_option_kind_is_refused_by_the_database(db_session):
    db_session.add(LabelOption(kind="colour", value="red"))
    with pytest.raises(IntegrityError):
        db_session.flush()
