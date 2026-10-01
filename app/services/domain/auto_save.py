"""The 自動保存 queue and every move between kinds, for lists and trips.

自動保存 is a 一般 row whose usage is 過去使用. The queue is capped - five list
slots, ten trips - and the oldest slot is dropped to make room, but never
silently: the first attempt raises `AutoSaveFull` naming what would go, and
only a confirmed retry drops it.

Nothing here raises `HTTPException`; the routers decide what a refusal looks
like over HTTP.
"""

from datetime import datetime

from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from app.constants import Kind, Usage
from app.models import PackingList, Trip

AUTO_SAVE_LIMIT: dict[type, int] = {PackingList: 5, Trip: 10}


class KindRefused(ValueError):
    """A move the model does not allow. The message is the 422's detail."""


class AutoSaveFull(Exception):
    """Setting 過去使用 would overflow the queue. `slot` is what would go."""

    def __init__(self, slot: list):
        super().__init__("auto-save is full")
        self.slot = slot


def _slot_key(model):
    """A round-trip pair of lists is one slot; every trip is its own.

    Coalescing to the id gives every unpaired list a key of its own and the
    two lists of a pair, which share a `pair_id`, a single shared one.
    """
    if model is PackingList:
        return func.coalesce(PackingList.pair_id, cast(PackingList.id, String))
    return cast(model.id, String)


def _auto_saved(model) -> tuple:
    return (model.kind == Kind.FREE, model.usage == Usage.PAST)


def count_slots(db: Session, model) -> int:
    """How many of the queue's slots are occupied."""
    key = _slot_key(model)
    return db.execute(
        select(func.count(func.distinct(key))).where(*_auto_saved(model))
    ).scalar_one()


def oldest_slot(db: Session, model) -> list:
    """The auto-saved rows of the slot that would be dropped next.

    Ordered by the slot's earliest `auto_saved_at`, then its lowest id - the
    tie-break is load-bearing, since `now()` is the transaction's start and
    two rows stamped in one transaction carry the same time. Only the
    auto-saved halves of a pair come back: a half still 使用中 is not part of
    the queue and is not dropped with it.
    """
    key = _slot_key(model)
    slot = db.execute(
        select(
            key.label("slot"),
            func.min(model.auto_saved_at).label("at"),
            func.min(model.id).label("id"),
        )
        .where(*_auto_saved(model))
        .group_by(key)
        .order_by("at", "id")
        .limit(1)
    ).first()
    if slot is None:
        return []
    return list(
        db.execute(select(model).where(*_auto_saved(model), key == slot.slot).order_by(model.id))
        .scalars()
        .all()
    )


def evict_next(db: Session, model) -> list:
    """What the next 過去使用 would drop, or nothing while there is room."""
    if count_slots(db, model) < AUTO_SAVE_LIMIT[model]:
        return []
    return oldest_slot(db, model)


def _adds_slot(db: Session, row) -> bool:
    """Whether `row` entering the queue would take a slot it does not share.

    The second half of a pair whose first half is already auto-saved joins
    that slot, so a full queue must not refuse it.
    """
    if not isinstance(row, PackingList) or row.pair_id is None:
        return True
    partner = db.execute(
        select(PackingList.id).where(
            *_auto_saved(PackingList),
            PackingList.pair_id == row.pair_id,
            PackingList.id != row.id,
        )
    ).first()
    return partner is None


def _enter_queue(db: Session, row, *, confirmed: bool, now: datetime) -> None:
    """Make room for `row` in 自動保存 - refusing, or dropping the oldest slot."""
    model = type(row)
    if _adds_slot(db, row) and count_slots(db, model) >= AUTO_SAVE_LIMIT[model]:
        slot = oldest_slot(db, model)
        if not confirmed:
            raise AutoSaveFull(slot)
        # Items and legs go by cascade; a list linked from a dropped trip's
        # leg is kept and unlinked, as on any trip delete.
        for dropped in slot:
            db.delete(dropped)
        db.flush()
    row.auto_saved_at = now


def apply_kind(db: Session, row, changes: dict, *, confirmed: bool, now: datetime) -> None:
    """Apply a PATCH's `kind` and `usage` to `row`, popping them from `changes`.

    Every check runs before anything is written, so a refusal leaves the row
    as it was. `None` means "not sent": the schemas refuse an explicit null.
    """
    kind = changes.pop("kind", None)
    usage = changes.pop("usage", None)
    if kind is None and usage is None:
        return
    if row.kind == Kind.TEMPLATE:
        raise KindRefused("A template's kind and usage cannot change.")
    if kind == Kind.TEMPLATE:
        raise KindRefused("A list or trip becomes a template only by creating one.")

    target_kind = kind or row.kind
    if usage is not None and target_kind != Kind.FREE:
        raise KindRefused("Only a free list or trip has a usage.")

    if target_kind == Kind.SAVED:
        row.kind, row.usage, row.auto_saved_at = Kind.SAVED, None, None
        return

    # 取消保存 lands on 未使用 unless the same request names another usage.
    current = row.usage if row.kind == Kind.FREE else Usage.UNUSED
    target_usage = usage or current
    if target_usage == Usage.PAST and current != Usage.PAST:
        _enter_queue(db, row, confirmed=confirmed, now=now)
    elif target_usage != Usage.PAST:
        row.auto_saved_at = None
    row.kind, row.usage = Kind.FREE, target_usage
