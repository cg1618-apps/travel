"""The rules about a list's contents: what a copy carries, where a variant goes, what a reset clears.

Nothing here raises `HTTPException`. The router decides what a refusal looks
like over HTTP; these functions only answer questions and perform changes.
"""

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.constants import Status
from app.models import PackingItem, PackingList


def copy_items(db: Session, source: PackingList, target: PackingList) -> None:
    """Copy `source`'s items onto `target`: definition carries, state resets.

    Nothing arrives pre-ticked. A duplicated list with its ticks intact is how
    you reach the airport certain you packed the charger.

    The list's own fields - departure_at, kind, usage, leg, pair_id,
    notes, archive_note, visibility - are deliberately not this function's business. They describe
    THAT list rather than its contents, and a template copied with
    `kind=template` is simply a second template.
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
                quantity_packed=0,
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


def reset_list(db: Session, packing_list: PackingList) -> None:
    """重設狀態: the copy rule's reset half, minus `no_need`.

    `no_need` is a choice about the list rather than progress through it, so
    it survives. `needs_double_check` is definition and survives too; only
    whether the check happened is cleared.
    """
    db.execute(
        update(PackingItem)
        .where(PackingItem.list_id == packing_list.id)
        .values(quantity_packed=0, double_checked=False)
    )
    db.execute(
        update(PackingItem)
        .where(PackingItem.list_id == packing_list.id, PackingItem.status == Status.PACKED)
        .values(status=Status.NOT_PACKED)
    )
    db.flush()

