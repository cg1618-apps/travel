"""The 自動保存 queue: slots, the limit, and every kind/usage move.

**A limit asserted against an empty queue passes because there was nothing to
drop.** `full_lists` and `full_trips` fill the queue to the limit and are the
only reason any refusal here can fail; each refusal has a mirror one under the
limit using the same rows. `auto_saved_at` is set explicitly: `now()` is the
transaction's start, so rows made in one test would otherwise tie.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.constants import Kind, Usage
from app.models import PackingItem, PackingList, Trip
from app.services.domain.auto_save import (
    AUTO_SAVE_LIMIT,
    AutoSaveFull,
    KindRefused,
    apply_kind,
    count_slots,
    evict_next,
    oldest_slot,
)

EPOCH = datetime(2026, 9, 1, tzinfo=timezone.utc)
NOW = EPOCH + timedelta(days=100)


def past(db, model, name, day, **fields):
    row = model(name=name, usage=Usage.PAST, auto_saved_at=EPOCH + timedelta(days=day), **fields)
    db.add(row)
    db.flush()
    return row


def free(db, model, name="new", **fields):
    row = model(name=name, **fields)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def full_lists(db_session):
    """Five auto-saved list slots, oldest first. Load-bearing."""
    return [past(db_session, PackingList, f"L{day}", day) for day in range(AUTO_SAVE_LIMIT[PackingList])]


@pytest.fixture
def full_trips(db_session):
    """Ten auto-saved trips, oldest first. Load-bearing."""
    return [past(db_session, Trip, f"T{day}", day) for day in range(AUTO_SAVE_LIMIT[Trip])]


# --- slots -------------------------------------------------------------------


def test_the_limits_are_five_lists_and_ten_trips():
    assert AUTO_SAVE_LIMIT == {PackingList: 5, Trip: 10}


@pytest.mark.parametrize("model", [PackingList, Trip])
def test_only_free_past_rows_occupy_slots(db_session, model):
    free(db_session, model)
    free(db_session, model, kind=Kind.SAVED)
    free(db_session, model, kind=Kind.TEMPLATE)
    assert count_slots(db_session, model) == 0
    past(db_session, model, "p", 0)
    assert count_slots(db_session, model) == 1


def test_a_list_pair_is_one_slot(db_session):
    past(db_session, PackingList, "去", 0, pair_id="p")
    past(db_session, PackingList, "回", 1, pair_id="p")
    assert count_slots(db_session, PackingList) == 1


def test_the_oldest_slot_ties_break_on_id(db_session):
    first = past(db_session, Trip, "a", 0)
    past(db_session, Trip, "b", 0)
    assert [row.id for row in oldest_slot(db_session, Trip)] == [first.id]


def test_the_oldest_pair_slot_holds_only_its_auto_saved_halves(db_session):
    gone = past(db_session, PackingList, "去", 0, pair_id="p")
    kept = free(db_session, PackingList, "回", pair_id="p", usage=Usage.IN_USE)
    assert oldest_slot(db_session, PackingList) == [gone]
    assert kept not in oldest_slot(db_session, PackingList)


def test_evict_next_is_empty_until_full(full_lists, db_session):
    assert [row.name for row in evict_next(db_session, PackingList)] == ["L0"]
    db_session.delete(full_lists[-1])
    db_session.flush()
    assert evict_next(db_session, PackingList) == []  # mirror


# --- setting past -------------------------------------------------------------


@pytest.mark.parametrize("model,fixture", [(PackingList, "full_lists"), (Trip, "full_trips")])
def test_past_when_full_is_refused_naming_the_oldest(request, db_session, model, fixture):
    rows = request.getfixturevalue(fixture)
    row = free(db_session, model)
    with pytest.raises(AutoSaveFull) as refused:
        apply_kind(db_session, row, {"usage": Usage.PAST}, confirmed=False, now=NOW)
    assert refused.value.slot == [rows[0]]
    assert row.usage == Usage.UNUSED  # nothing changed


@pytest.mark.parametrize("model,fixture", [(PackingList, "full_lists"), (Trip, "full_trips")])
def test_past_when_full_and_confirmed_drops_the_oldest(request, db_session, model, fixture):
    rows = request.getfixturevalue(fixture)
    oldest_id = rows[0].id
    row = free(db_session, model)
    apply_kind(db_session, row, {"usage": Usage.PAST}, confirmed=True, now=NOW)
    db_session.flush()
    assert db_session.get(model, oldest_id) is None
    assert (row.usage, row.auto_saved_at) == (Usage.PAST, NOW)
    assert count_slots(db_session, model) == AUTO_SAVE_LIMIT[model]


@pytest.mark.parametrize("model,fixture", [(PackingList, "full_lists"), (Trip, "full_trips")])
def test_past_under_the_limit_is_not_refused(request, db_session, model, fixture):
    rows = request.getfixturevalue(fixture)
    db_session.delete(rows[-1])
    db_session.flush()
    row = free(db_session, model)
    apply_kind(db_session, row, {"usage": Usage.PAST}, confirmed=False, now=NOW)
    assert row.auto_saved_at == NOW


def test_a_dropped_list_takes_its_items(full_lists, db_session):
    full_lists[0].items.append(PackingItem(name="傘", position=0))
    db_session.flush()
    item_id = full_lists[0].items[0].id
    apply_kind(db_session, free(db_session, PackingList), {"usage": Usage.PAST}, confirmed=True, now=NOW)
    db_session.flush()
    db_session.expire_all()
    assert db_session.get(PackingItem, item_id) is None


def test_the_second_half_of_a_pair_adds_no_slot(full_lists, db_session):
    full_lists[-1].pair_id = "p"
    other_half = free(db_session, PackingList, "回", pair_id="p")
    apply_kind(db_session, other_half, {"usage": Usage.PAST}, confirmed=False, now=NOW)
    assert other_half.usage == Usage.PAST


def test_resending_past_keeps_the_stamp_and_is_not_refused(full_lists, db_session):
    row = full_lists[2]
    stamp = row.auto_saved_at
    apply_kind(db_session, row, {"usage": Usage.PAST}, confirmed=False, now=NOW)
    assert row.auto_saved_at == stamp


@pytest.mark.parametrize("usage", [Usage.IN_USE, Usage.UPCOMING, Usage.UNUSED])
def test_leaving_past_clears_the_stamp(db_session, usage):
    row = past(db_session, Trip, "p", 0)
    apply_kind(db_session, row, {"usage": usage}, confirmed=False, now=NOW)
    assert (row.usage, row.auto_saved_at) == (usage, None)


# --- 保存 and 取消保存 -----------------------------------------------------------


@pytest.mark.parametrize("model", [PackingList, Trip])
def test_saving_a_free_or_auto_saved_row_clears_usage(db_session, model):
    for row in (free(db_session, model), past(db_session, model, "p", 0)):
        apply_kind(db_session, row, {"kind": Kind.SAVED}, confirmed=False, now=NOW)
        assert (row.kind, row.usage, row.auto_saved_at) == (Kind.SAVED, None, None)


def test_saving_is_never_refused_by_the_limit(full_lists, db_session):
    apply_kind(db_session, full_lists[0], {"kind": Kind.SAVED}, confirmed=False, now=NOW)
    assert full_lists[0].kind == Kind.SAVED


def test_unsaving_returns_a_row_to_free_unused(db_session):
    row = free(db_session, PackingList, kind=Kind.SAVED)
    apply_kind(db_session, row, {"kind": Kind.FREE}, confirmed=False, now=NOW)
    assert (row.kind, row.usage) == (Kind.FREE, Usage.UNUSED)


def test_unsaving_straight_to_past_goes_through_the_limit(full_lists, db_session):
    row = free(db_session, PackingList, kind=Kind.SAVED)
    with pytest.raises(AutoSaveFull):
        apply_kind(db_session, row, {"kind": Kind.FREE, "usage": Usage.PAST}, confirmed=False, now=NOW)
    assert row.kind == Kind.SAVED


# --- refusals ------------------------------------------------------------------


@pytest.mark.parametrize(
    "start,changes",
    [
        ({"kind": Kind.FREE}, {"kind": Kind.TEMPLATE}),
        ({"kind": Kind.TEMPLATE}, {"kind": Kind.SAVED}),
        ({"kind": Kind.TEMPLATE}, {"usage": Usage.IN_USE}),
        ({"kind": Kind.SAVED}, {"usage": Usage.IN_USE}),
    ],
)
def test_impossible_moves_are_refused(db_session, start, changes):
    row = free(db_session, Trip, **start)
    with pytest.raises(KindRefused):
        apply_kind(db_session, row, dict(changes), confirmed=False, now=NOW)


def test_a_free_row_may_change_usage(db_session):
    # Mirror of the refusal above for `usage` on a saved row.
    row = free(db_session, Trip)
    apply_kind(db_session, row, {"usage": Usage.IN_USE}, confirmed=False, now=NOW)
    assert row.usage == Usage.IN_USE
