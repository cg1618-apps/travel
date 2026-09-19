"""The rules about lists: what fills the cap, what eviction destroys, what a
copy carries.

Nothing here raises `HTTPException`. The router decides what a refusal looks
like over HTTP; these functions only answer questions and perform changes.
"""

from sqlalchemy import String, cast, func, select, update
from sqlalchemy.orm import Session

from app.constants import LabelKind, Status
from app.models import LabelOption, PackingItem, PackingList

#: How many working lists may exist at once. Saved lists and templates are
#: exempt, so this is a cap on clutter rather than on how much you may keep.
SLOT_CAP = 3

#: A slot is one working list, or one round-trip pair. The two lists of a pair
#: share a `pair_id`, so coalescing to the id gives every unpaired list a slot
#: key of its own and the pair a single shared one.
SLOT_KEY = func.coalesce(PackingList.pair_id, cast(PackingList.id, String))

#: Neither saved nor a template. Both flags are independent, so this is an AND
#: of two negatives rather than a single "kind" check.
_WORKING = (PackingList.saved.is_(False), PackingList.template.is_(False))


def count_slots(db: Session) -> int:
    """How many of the cap's slots are currently occupied."""
    return db.execute(
        select(func.count(func.distinct(SLOT_KEY))).where(*_WORKING)
    ).scalar_one()


def oldest_slot(db: Session) -> list[PackingList]:
    """Every list in the slot that would be evicted next, oldest first.

    A pair comes back as two rows, because evicting a slot destroys both -
    leaving half a round trip behind would be worse than leaving none of it.

    Ordering breaks ties on `id`, and that is load-bearing rather than
    defensive. `created_at` defaults to `now()`, which in PostgreSQL is the
    TRANSACTION's start time, so every list created in one transaction carries
    an identical timestamp - and which one is "oldest" would otherwise be
    whatever the planner felt like returning.
    """
    slot = db.execute(
        select(
            SLOT_KEY.label("slot"),
            func.min(PackingList.created_at).label("created_at"),
            func.min(PackingList.id).label("id"),
        )
        .where(*_WORKING)
        .group_by(SLOT_KEY)
        .order_by("created_at", "id")
        .limit(1)
    ).first()

    if slot is None:
        return []

    return list(
        db.execute(
            select(PackingList)
            .where(*_WORKING, SLOT_KEY == slot.slot)
            .order_by(PackingList.id)
        )
        .scalars()
        .all()
    )


def evict(db: Session, slot: list[PackingList]) -> None:
    """Destroy a slot. Items go with their lists by ON DELETE CASCADE."""
    for packing_list in slot:
        db.delete(packing_list)
    db.flush()


def copy_items(db: Session, source: PackingList, target: PackingList) -> None:
    """Copy `source`'s items onto `target`: definition carries, state resets.

    Nothing arrives pre-ticked. A duplicated list with its ticks intact is how
    you reach the airport certain you packed the charger.

    The list's own fields - departure_at, saved, template, leg, pair_id,
    visibility - are deliberately not this function's business. They describe
    THAT list rather than its contents, and a template copied with
    `template=True` is simply a second template.
    """
    for item in source.items:
        db.add(
            PackingItem(
                list_id=target.id,
                # Carried: what the item IS.
                name=item.name,
                category=item.category,
                bag=item.bag,
                quantity=item.quantity,
                unit=item.unit,
                timing=item.timing,
                needs_double_check=item.needs_double_check,
                notes=item.notes,
                position=item.position,
                # Reset: what was true of it on the old trip.
                status=Status.NOT_PACKED,
                quantity_packed=0,
                double_checked=False,
            )
        )
    db.flush()


# --------------------------------------------------------------------------
# Common options
#
# `label_option` rows are suggestions for the free-text `category` and `bag`
# fields. An item holds the text itself and may always carry a value that is
# not among them - which is what makes a rename a rewrite rather than a
# repointing.
# --------------------------------------------------------------------------

#: Which item column each kind of option suggests values for.
_COLUMN_FOR_KIND = {LabelKind.CATEGORY: "category", LabelKind.BAG: "bag"}


def remember_label(db: Session, kind: LabelKind, value: str | None) -> None:
    """Record a typed value as a suggestion, if it is not one already."""
    if not value:
        return
    already = db.execute(
        select(LabelOption.id).where(
            LabelOption.kind == kind, LabelOption.value == value
        )
    ).first()
    if already:
        return

    highest = db.execute(
        select(func.max(LabelOption.position)).where(LabelOption.kind == kind)
    ).scalar()
    db.add(
        LabelOption(
            kind=kind, value=value, position=0 if highest is None else highest + 1
        )
    )
    db.flush()


def remember_item_labels(db: Session, item: PackingItem) -> None:
    """Record both of an item's free-text values."""
    remember_label(db, LabelKind.CATEGORY, item.category)
    remember_label(db, LabelKind.BAG, item.bag)


def count_items_using(db: Session, option: LabelOption) -> int:
    """How many items carry this option's value, so a rename can say so first."""
    column = getattr(PackingItem, _COLUMN_FOR_KIND[LabelKind(option.kind)])
    return db.execute(
        select(func.count()).select_from(PackingItem).where(column == option.value)
    ).scalar_one()


def rename_option(db: Session, option: LabelOption, new_value: str) -> int:
    """Rename an option, rewriting every item that used it. Returns how many.

    Renaming onto a value that already exists is a **merge**: the items are
    rewritten either way, and then the source row is deleted rather than
    updated, because the unique constraint on (kind, value) would refuse the
    update outright. Merging is the useful reading of that collision - two
    spellings of one thing is exactly what a rename is usually fixing.
    """
    if new_value == option.value:
        return 0

    column_name = _COLUMN_FOR_KIND[LabelKind(option.kind)]
    column = getattr(PackingItem, column_name)
    rewritten = db.execute(
        update(PackingItem)
        .where(column == option.value)
        .values({column_name: new_value})
    ).rowcount

    collision = db.execute(
        select(LabelOption).where(
            LabelOption.kind == option.kind,
            LabelOption.value == new_value,
            LabelOption.id != option.id,
        )
    ).scalar_one_or_none()

    if collision is not None:
        db.delete(option)
    else:
        option.value = new_value

    db.flush()
    return rewritten
