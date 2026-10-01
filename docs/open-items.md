# Open items

Known defects and unmade decisions that nobody is working on. **Everything
here is open by definition** — there is no status column, no claiming, and no
lifecycle. An item is fixed by deleting it in the same change that fixes it,
and the commit and pull request are the record of that.

Nothing here blocks using the application.

This is not a work log and not a plan. What a session is currently doing lives
in the branch and the pull request.

## Backend

**A race on a leg's packing-list link can answer `500` instead of `409`.**
`create_leg` and `update_leg` in `app/routers/trip.py` call `remember_label`
for the leg's `ticket_type` before `_commit`. `remember_label`
(`app/services/domain/labels.py`) runs a `SELECT`, which autoflushes the
pending leg, and then flushes its own new option — both outside `_commit`'s
`try`. So when a concurrent request links the same list between `_check_link`
and the commit, the unique constraint on `trip_leg.packing_list_id` fires
during that flush, escapes as an unhandled `IntegrityError`, and the caller
gets a `500` rather than the `409` the docstring promises. It only happens
when the leg carries a `ticket_type`; without one, the flush happens inside
`_commit` and the `409` is correct.

**`_commit` in `app/routers/trip.py` reports every `IntegrityError` as "That
packing list is already linked to another leg."** It is written for the
unique constraint on `trip_leg.packing_list_id`, but it catches whatever the
commit raises: the foreign key failing because the list was deleted after
`_check_link` looked, or two requests remembering the same new `ticket_type`
at once (`uq_label_option_kind_value`). Each comes back as a `409` with a
message about linking that is not what happened.

**The duplicate-departure race path is untested.** `_commit_departure` in
`app/routers/transport.py` turns an `IntegrityError` from the unique
constraint into the same `409` the pre-check gives, and that is the only thing
that holds when two requests add one departure at once. Every test in
`tests/api/test_transport_router.py` is refused by `_refuse_duplicate` first,
so the fallback could be removed or broken and the suite would stay green.

**Merging one location into another is untested.** `rename_option` in
`app/services/domain/labels.py` handles a rename onto an existing value as a
merge, for every kind through `COLUMN_FOR_KIND`. The merge is tested for
`category` only (`test_renaming_onto_an_existing_option_merges` in
`tests/api/test_label_option_router.py`) and a location is tested only for a
plain rename, so a merge that broke for `location` alone would pass.

## Sheet importer

**A second mode-less Transportation row for the same route overwrites the
first one's note.** `_parse_transport` in
`app/services/sheet_import/parse.py` sets `route.notes = "時間 <value>"` for a
row with no `交通工具`, assigning rather than appending. When two such rows name
the same 目標起點 and 目標終點, only the last `時間` survives, and nothing is
reported.

**A Transportation row with neither endpoint is reported as "None has no
destination".** The same function builds the skip line from
`start or end`, which is `None` when both cells are blank, so the report prints
the literal word `None` instead of saying the row has no start and no
destination.

**Departure times that carry seconds are truncated, not rounded, and not
reported.** `_parse_time_cell` in `app/services/sheet_import/parse.py` drops
the seconds of a `datetime` or `time` cell with `replace(second=0)`, while a
numeric cell is rounded to the nearest minute. A cell holding `07:14:59`
imports as 07:14, and the report does not mention it.

## Frontend

**A failed write shows nothing.** Most mutations are fire-and-forget
`.mutate()` calls with no `onError`: every item patch, add and delete and the
reset and departure-date patch on `src/pages/PackingList.jsx`; every route and
option write and the departure delete on `src/pages/Transport.jsx`; the trip
and leg field patches and the deletes on `src/pages/Trip.jsx`; and the rename
and delete on `src/pages/Options.jsx`. Only the departure adder, a leg's times
and its packing-list link await the write and show a refusal. `useApiMutation` in
`src/hooks/useApiQuery.js` only invalidates on success, so when the server
refuses or is unreachable the screen gives no sign that the change was not
saved. `PackingLists.jsx` is the one page that handles errors. Nor are the
buttons disabled while a write is pending — 重設狀態 and the reset dialog's
重設 can be pressed again before the first reset answers. Whether failures get
one app-wide treatment (a toast, a mutation-cache `onError`) or a per-page one
is undecided.

**The row menu does not behave like a menu for keyboard and screen-reader
users.** `RowMenu` in `src/components/RowMenu.jsx` declares `role="menu"` and
focuses its first item, but arrow keys do not move between items, and closing
it does not return focus to the ⋯ button that opened it — focus is left on
`document.body`. Its click guard also ignores any click not preceded by a
`pointerdown` or `keydown` since it opened, which is what stops the tail of a
long-press acting on iOS; an assistive technology that activates an item by a
synthetic click with neither event is ignored too, so the item does nothing.

**A checklist group repeats its own name for a variant without a detail.**
`Group` in `src/components/Checklist.jsx` labels each variant `item.detail ||
item.name`. When two items share a name and one has no `detail`, that line reads
the group's name again under the group's heading, so two lines in one group can
be indistinguishable.

**Escape in a departure adder leaves the old error on screen.** In
`DepartureAdder` in `src/pages/Transport.jsx`, Escape clears the text through
`keysFor(submit, () => setText(''))` but not the error, so 時間格式不對 or
這班已經有了 stays under an empty input until the next keystroke.

**The Transport and Trip pages clip what overflows instead of scrolling
it.** Both wrap their content in `<main className="... overflow-x-hidden ...">`
(`Transport.jsx` and the `shell` in `Trip.jsx`). Anything wider than a phone's
screen is cut off at the edge with no way to reach it, and the clipping also
hides the overflow that would otherwise show a layout is too wide.

**No component has a test.** The vitest suite covers `src/lib/` only, and
there is no DOM-testing library in `package.json`. So the gesture rules —
`useLongPress` never firing both the long-press and the click, `RowMenu`
ignoring the click that ends a long-press — and everything on `Trip.jsx` are
checked by nobody but a person with a phone. Whether to add component tests,
and for which screens, is undecided.
