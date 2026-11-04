"""The rules about a list's contents: what a copy carries, where a new or
moved item goes, what order a list may take, what a reset clears.

A **group** is the items on one list sharing a `category`; null is a group of
its own. Groups have no table and no order column: a group sits where its
items sit in `position`, so keeping each group's items adjacent is what keeps
the groups whole. Every placement here preserves that, and `set_order`
refuses an order that breaks it. The rule itself is
`app.services.domain.ordering`'s, shared with notes and transport routes.

Nothing here raises `HTTPException`. The router decides what a refusal looks
like over HTTP; these functions only answer questions and perform changes.
"""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.constants import Status
from app.models import PackingItem, PackingList
from app.services.domain import ordering
from app.services.domain.ordering import apply_order, check_groups, check_order


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

    Every later item on the SAME list shifts down by one, so a variant lands
    under the row it was added from.
    """
    return ordering.insert_after(db, PackingItem, {"list_id": after.list_id}, after)


def next_position(db: Session, list_id: int, *, exclude_id: int | None = None) -> int:
    """One past the end of THIS list, leaving `exclude_id` out of the count.

    Scoped to the list rather than global: a shared counter would leave a new
    list's first item at position 400 and sort correctly by accident, until
    something started comparing positions between lists.
    """
    return ordering.next_position(db, PackingItem, {"list_id": list_id}, exclude_id=exclude_id)


def place_in_group(
    db: Session, list_id: int, category: str | None, *, exclude_id: int | None = None
) -> int:
    """Make room at the end of `category`'s group on this list; return that
    position. The group rule is `ordering.place_in_group`'s."""
    return ordering.place_in_group(
        db, PackingItem, {"list_id": list_id}, "category", category, exclude_id=exclude_id
    )


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

    check_order(item_ids, items, noun="item", where="on this list")
    check_groups(
        item_ids,
        {item_id: item.category for item_id, item in items.items()},
        noun="item",
        describe=_group_name,
    )

    apply_order(items, item_ids)
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

