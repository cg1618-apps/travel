"""A whole order, set in one request: the rule every reorder endpoint shares.

A caller sends the ids of every row in a set - the items of a list, the
routes, the options of a route - in the order they should read, and the rows
take positions 0..n-1. The order must name every row exactly once and nothing
else: a partial order would leave the unnamed rows colliding with the named
ones, and a foreign id would move a row that belongs to another set.

Nothing here raises `HTTPException`; the routers turn `OrderRefused` into a 422.
"""

from collections.abc import Mapping, Sequence


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
