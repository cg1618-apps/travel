# One whole-order rule and one group rule, shared by every ordered table

Packing items, routes, route options, route notes and 筆記 are all ordered by a
request naming the whole set once. The check — every id once, nothing foreign —
lives in `app/services/domain/ordering.py`, and every order endpoint shares it.

**The group machinery is there too**: `check_groups`, and `place_in_group` /
`insert_after` / `next_position` over any model with a `position`, a group
column and a `scope`. `app/services/domain/packing.py` keeps thin wrappers with
its own names.

Rejected:

- **Copying the helpers per table.** Three copies of a rule that has already
  had one subtle bug (`IS NOT DISTINCT FROM` for the null group) is three
  places to get it wrong.
- **A `position` PATCH per row** for reordering. It is one write per row a drag
  passes, with the positions inconsistent between them.
