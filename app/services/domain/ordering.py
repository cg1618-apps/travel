"""A whole order, set in one request: the rule every reorder endpoint shares.

A caller sends the ids of every row in a set - the items of a list, the
routes, the options of a route - in the order they should read, and the rows
take positions 0..n-1. The order must name every row exactly once and nothing
else: a partial order would leave the unnamed rows colliding with the named
ones, and a foreign id would move a row that belongs to another set.

Nothing here raises `HTTPException`; the routers turn `OrderRefused` into a 422.

The second half of the module is groups: placing a row at the end of its
group, and refusing an order that splits one.
"""

from collections.abc import Callable, Mapping, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session


class OrderRefused(ValueError):
    """An order that will not be applied. The message is the 422's `detail`."""


def check_order(ids: Sequence[int], known: Mapping[int, object], *, noun: str, where: str) -> None:
    """Refuse `ids` unless it names every key of `known` exactly once.

    `noun` and `where` only word the refusal - "item", "on this list".
    """
    seen: set[int] = set()
    for row_id in ids:
        if row_id in seen:
            raise OrderRefused(f"{noun.capitalize()} {row_id} appears more than once in the order.")
        seen.add(row_id)
    foreign = [row_id for row_id in ids if row_id not in known]
    if foreign:
        raise OrderRefused(f"Not {where}: {noun}s {', '.join(map(str, foreign))}.")
    missing = sorted(set(known) - seen)
    if missing:
        raise OrderRefused(
            f"The order must name every {noun} {where}; missing {noun}s "
            f"{', '.join(map(str, missing))}."
        )


def apply_order(rows: Mapping[int, object], ids: Sequence[int]) -> None:
    """Give each row its index in `ids` as its `position`. Check first."""
    for position, row_id in enumerate(ids):
        rows[row_id].position = position


# --- groups -------------------------------------------------------------------
#
# A **group** is the rows of one set sharing a value in a group column - a
# packing item's `category`, a note's or a transport route's `group_name` -
# with null a group of its own. Groups have no table and no order column: a
# group sits where its rows sit in `position`, so keeping each group's rows
# adjacent is what keeps the groups whole. The helpers below are that rule,
# written once for every set that has groups.
#
# `scope` narrows the set: `{"list_id": 3}` for the items of one list, `{}`
# for every note or every route.


def check_groups(
    ids: Sequence[int],
    group_of: Mapping[int, object],
    *,
    noun: str,
    describe: Callable[[object], str],
) -> None:
    """Refuse an order that splits a group: one group value in two runs.

    Run after `check_order`, so every id is known. `describe` names a group in
    the refusal - 'the "衣服" group', 'the uncategorised group'.
    """
    values = [group_of[row_id] for row_id in ids]
    runs = [v for i, v in enumerate(values) if i == 0 or v != values[i - 1]]
    started: set[object] = set()
    for value in runs:
        if value in started:
            raise OrderRefused(
                f"The order splits {describe(value)}: a group's {noun}s must be adjacent."
            )
        started.add(value)


def _scoped(query, model, scope: Mapping[str, object]):
    for column, value in scope.items():
        query = query.where(getattr(model, column) == value)
    return query


def next_position(
    db: Session, model, scope: Mapping[str, object], *, exclude_id: int | None = None
) -> int:
    """One past the end of the set, leaving `exclude_id` out of the count."""
    query = _scoped(select(func.max(model.position)), model, scope)
    if exclude_id is not None:
        query = query.where(model.id != exclude_id)
    highest = db.execute(query).scalar()
    return 0 if highest is None else highest + 1


def insert_after(db: Session, model, scope: Mapping[str, object], after) -> int:
    """Make room directly after `after` in its set; return that position.

    Every later row of the SAME set shifts down by one, in the caller's
    transaction, so positions stay contiguous.
    """
    db.execute(
        _scoped(update(model), model, scope)
        .where(model.position > after.position)
        .values(position=model.position + 1)
    )
    return after.position + 1


def place_in_group(
    db: Session,
    model,
    scope: Mapping[str, object],
    group_column: str,
    group,
    *,
    exclude_id: int | None = None,
) -> int:
    """Make room at the end of `group`'s run in the set; return that position.

    Directly after the group's last row, shifting later rows down as
    `insert_after` does, so the group stays one block. A group nobody in the
    set carries yet starts one past the end. `exclude_id` is the row being
    moved, which must not count as a member of the group it is joining - nor,
    at the end of the set, as the row to go after.

    `IS NOT DISTINCT FROM` rather than `=`, so null finds the null group:
    `column = NULL` matches nothing.
    """
    query = _scoped(select(model), model, scope).where(
        getattr(model, group_column).is_not_distinct_from(group)
    )
    if exclude_id is not None:
        query = query.where(model.id != exclude_id)
    last = db.scalars(query.order_by(model.position.desc()).limit(1)).first()
    if last is None:
        return next_position(db, model, scope, exclude_id=exclude_id)
    return insert_after(db, model, scope, last)


def ungrouped_or_named(group: str | None) -> str:
    """How a refusal names a group of notes or routes."""
    return "the ungrouped group" if group is None else f'the "{group}" group'
