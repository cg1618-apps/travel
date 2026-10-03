"""The rules about a list's contents: what a copy carries, where a new or
moved item goes, what order a list may take, what a reset clears.

A **group** is the items on one list sharing a `category`; null is a group of
its own. Groups have no table and no order column: a group sits where its
items sit in `position`, so keeping each group's items adjacent is what keeps
the groups whole. Every placement here preserves that, and `set_order`
refuses an order that breaks it.

Nothing here raises `HTTPException`. The router decides what a refusal looks
like over HTTP; these functions only answer questions and perform changes.
"""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.constants import Status
from app.models import PackingItem, PackingList


def copy_items(db: Session, source: PackingList, target: PackingList) -> None:
    """Copy `source`'s items onto `target`: definition carries, state resets.

    Nothing arrives pre-ticked. A duplicated list with its ticks intact is how
    you reach the airport certain you packed the charger.

    The list's own fields - departure_at, kind, usage, leg, pair_id, notes,
    archive_note, visibility - are deliberately not this function's business.
    They describe THAT list rather than its contents, and a list copied with
    `kind=template` is simply a new template.
    """
    for item in source.items:
        db.add(
            PackingItem(
                list_id=target.id,
                # Carried: what the item IS.
                name=item.name,
                detail=item.detail,
                category=item.category,
                bag=item.bag,
                location=item.location,
                need=item.need,
                quantity=item.quantity,
                unit=item.unit,
                timing=item.timing,
                needs_double_check=item.needs_double_check,
                notes=item.notes,
                position=item.position,
                # Reset: what was true of it on the old trip.
                status=Status.NOT_PACKED,
                quantity_packed=None,
                double_checked=False,
            )
        )
    db.flush()


def insert_after(db: Session, after: PackingItem) -> int:
    """Make room directly after `after` on its own list; return that position.

    Every later item on the SAME list shifts down by one, in the caller's
    transaction, so positions stay contiguous and a variant lands under the
    row it was added from.
    """
    db.execute(
        update(PackingItem)
        .where(PackingItem.list_id == after.list_id, PackingItem.position > after.position)
        .values(position=PackingItem.position + 1)
    )
    return after.position + 1


def next_position(db: Session, list_id: int, *, exclude_id: int | None = None) -> int:
    """One past the end of THIS list, leaving `exclude_id` out of the count.

    Scoped to the list rather than global: a shared counter would leave a new
    list's first item at position 400 and sort correctly by accident, until
    something started comparing positions between lists.
    """
    query = select(func.max(PackingItem.position)).where(PackingItem.list_id == list_id)
    if exclude_id is not None:
        query = query.where(PackingItem.id != exclude_id)
    highest = db.execute(query).scalar()
    return 0 if highest is None else highest + 1


def place_in_group(
    db: Session, list_id: int, category: str | None, *, exclude_id: int | None = None
) -> int:
    """Make room at the end of `category`'s group on this list; return that position.

    Directly after the group's last item, shifting later items down as
    `insert_after` does, so the group stays one block. A category nobody on
    the list carries yet starts a new group one past the end. `exclude_id` is
    the item being moved, which must not count as a member of the group it is
    joining - nor, at the end of the list, as the item to go after.

    `IS NOT DISTINCT FROM` rather than `=`, so null finds the uncategorised
    group: `category = NULL` matches nothing.
    """
    query = select(PackingItem).where(
        PackingItem.list_id == list_id, PackingItem.category.is_not_distinct_from(category)
    )
    if exclude_id is not None:
        query = query.where(PackingItem.id != exclude_id)
    last = db.scalars(query.order_by(PackingItem.position.desc()).limit(1)).first()
    if last is None:
        return next_position(db, list_id, exclude_id=exclude_id)
    return insert_after(db, last)


class OrderRefused(ValueError):
    """An order `set_order` will not apply. The message is the 422's `detail`."""


def _group_name(category: str | None) -> str:
    return "the uncategorised group" if category is None else f'the "{category}" group'


def set_order(db: Session, packing_list: PackingList, item_ids: list[int]) -> None:
    """Give the list's items positions 0..n-1 in the order of `item_ids`.

    The order must name every item on the list exactly once - a partial order
    would leave the unnamed items colliding with the named ones - and must
    keep each group adjacent. Everything is checked before anything is
    written, so a refusal changes nothing.
    """
    items = {
        item.id: item
        for item in db.scalars(select(PackingItem).where(PackingItem.list_id == packing_list.id))
    }

    seen: set[int] = set()
    for item_id in item_ids:
        if item_id in seen:
            raise OrderRefused(f"Item {item_id} appears more than once in the order.")
        seen.add(item_id)
    foreign = [item_id for item_id in item_ids if item_id not in items]
    if foreign:
        raise OrderRefused(f"Not on this list: items {', '.join(map(str, foreign))}.")
    missing = sorted(set(items) - seen)
    if missing:
        raise OrderRefused(
            f"The order must name every item on the list; missing items "
            f"{', '.join(map(str, missing))}."
        )

    # One entry per run of equal categories; a category with two runs is a
    # group the order would split.
    categories = [items[item_id].category for item_id in item_ids]
    runs = [c for i, c in enumerate(categories) if i == 0 or c != categories[i - 1]]
    started: set[str | None] = set()
    for category in runs:
        if category in started:
            raise OrderRefused(
                f"The order splits {_group_name(category)}: a group's items must be adjacent."
            )
        started.add(category)

    for position, item_id in enumerate(item_ids):
        items[item_id].position = position
    db.flush()


def reset_list(db: Session, packing_list: PackingList) -> None:
    """重設狀態: the copy rule's reset half, minus `no_need`.

    `packed` becomes `not_packed`, 已打包數量 cleared (back to no value, as
    on a new item) and `double_checked` false. `no_need` is a choice about
    the list rather than progress through it, so it survives.
    `needs_double_check` is definition and survives too; only whether the
    check happened is cleared.
    """
    db.execute(
        update(PackingItem)
        .where(PackingItem.list_id == packing_list.id)
        .values(quantity_packed=None, double_checked=False)
    )
    db.execute(
        update(PackingItem)
        .where(PackingItem.list_id == packing_list.id, PackingItem.status == Status.PACKED)
        .values(status=Status.NOT_PACKED)
    )
    db.flush()

