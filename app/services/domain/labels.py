"""Common options: remembered values behind the free-text fields.

`label_option` rows are suggestions. The row that uses a value holds the text
itself and may always carry a value that is not among them - which is what
makes a rename a rewrite rather than a repointing. Each kind suggests values
for exactly one column, named in `COLUMN_FOR_KIND`.
"""

from sqlalchemy import func, select, update
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.constants import LabelKind
from app.models import LabelOption, PackingItem, TripLeg

#: Which column each kind of option suggests values for.
COLUMN_FOR_KIND: dict[LabelKind, InstrumentedAttribute] = {
    LabelKind.CATEGORY: PackingItem.category,
    LabelKind.BAG: PackingItem.bag,
    LabelKind.LOCATION: PackingItem.location,
    LabelKind.TICKET_TYPE: TripLeg.ticket_type,
}


def remember_label(db: Session, kind: LabelKind, value: str | None) -> None:
    """Record a typed value as a suggestion, if it is not one already."""
    if not value:
        return
    already = db.execute(
        select(LabelOption.id).where(LabelOption.kind == kind, LabelOption.value == value)
    ).first()
    if already:
        return

    highest = db.execute(
        select(func.max(LabelOption.position)).where(LabelOption.kind == kind)
    ).scalar()
    db.add(LabelOption(kind=kind, value=value, position=0 if highest is None else highest + 1))
    db.flush()


def remember_item_labels(db: Session, item: PackingItem) -> None:
    """Record every free-text value an item carries."""
    remember_label(db, LabelKind.CATEGORY, item.category)
    remember_label(db, LabelKind.BAG, item.bag)
    remember_label(db, LabelKind.LOCATION, item.location)


def count_using(db: Session, option: LabelOption) -> int:
    """How many rows carry this option's value, so a rename can say so first."""
    column = COLUMN_FOR_KIND[LabelKind(option.kind)]
    return db.execute(
        select(func.count()).select_from(column.class_).where(column == option.value)
    ).scalar_one()


def rename_option(db: Session, option: LabelOption, new_value: str) -> int:
    """Rename an option, rewriting every row that used it. Returns how many.

    Renaming onto a value that already exists is a **merge**: the rows are
    rewritten either way, and then the source option is deleted rather than
    updated, because the unique constraint on (kind, value) would refuse the
    update outright. Merging is the useful reading of that collision - two
    spellings of one thing is exactly what a rename is usually fixing.
    """
    if new_value == option.value:
        return 0

    column = COLUMN_FOR_KIND[LabelKind(option.kind)]
    rewritten = db.execute(
        update(column.class_).where(column == option.value).values({column.key: new_value})
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
