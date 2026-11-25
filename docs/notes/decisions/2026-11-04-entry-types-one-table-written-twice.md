# Entry types are one table, written twice

What each transport type shows and which labels it carries is a table,
`LEG_TYPES`. The form needs it to lay itself out; the server needs it to refuse
a switch the type cannot have and to compute readiness. It is written in
`app/services/domain/leg_types.py` and again in `frontend/src/lib/legTypes.js`,
as the dashboard rule is, rather than served: the form needs it before it has
loaded anything, and the readable sheet tab needs it with no browser.
`tests/unit/test_leg_types.py` spells the table out in full, so changing a
type's form is a visible edit to a test rather than a quiet edit to one copy.

**A capability is one of four strings** — `fixed`, `optional_on`,
`optional_off`, `absent` — rather than a pair of "has a switch" and "default".
Four named states read the same in both languages, and the impossible
combination ("no switch, default off") has no spelling.

**The `has_*` switches are columns, not derived.** A label's state is partly
the type's and partly the entry's own choice (a 火車 ticket bought at the
station has no 已取票), so it is stored per entry. The router constrains them by
type, not a CHECK: a CHECK would need the table in SQL, a third copy.

**Changing a type resets the switches the request does not name**, because a
switch only means something for the type it was set on: keeping a car's
`has_collected` (always false) would make a car turned into a 火車 lose 已取票
silently. **Values of fields the type does not show are kept**, for the
opposite reason: a seat or a ride type is data the owner typed, and a mistaken
type change should not destroy it.
