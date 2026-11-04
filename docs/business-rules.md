# Business rules

Last verified: 2026-11-04

**What this is for.** The rules that are not visible in the schema — what kind
a list or trip is and how it moves between kinds, what fills 自動保存 and what
dropping a slot destroys, what a copy carries, and how the status and check
fields relate. Column-level facts live in `data-model.md`; why a rule is shaped
this way lives in `notes/decisions.md`.

These live in `app/services/domain/`, not in the routers: kinds, usage and the
自動保存 queue in `auto_save.py`, the copy and reset rules in `packing.py`, the
whole-order rule in `ordering.py`, the
common-options rules in `labels.py` and the trip-copy rule in `trip.py`. The sheet importer is `app/services/sheet_import/`. A router owns
wiring and status codes; a rule reimplemented in a second endpoint is a rule
with two answers.

## Kinds, usage and 自動保存

Lists and trips share one model. Every row has exactly one **kind**, and a
一般 row also has a **usage** (狀態):

| Kind (`kind`) | 中文 | Made by | `usage` | Limit |
| --- | --- | --- | --- | --- |
| `template` | 範本 | Creating one as 範本 (blank or copied), or 當作範本 on any list or trip, which **copies** it | null | none |
| `saved` | 保存 | 保存 on a 一般 or 自動保存 row, which **moves** it | null | none |
| `free` | 一般 | The ordinary create | `in_use` 使用中 · `upcoming` 未來使用 · `unused` 未使用 | none |
| `free` + `past` | 自動保存 | Setting a 一般 row to `past` 過去使用 | `past` | lists 5 slots, trips 10 |

**自動保存 is not a stored kind.** It is `kind = 'free' AND usage = 'past'`, so
"a 一般 row marked 過去使用 is auto-saved" is true by construction rather than
kept in step by code. The database's check constraints make every other
combination unstorable (`data-model.md`).

- **A new 一般 row starts `unused`.** Usage changes only by hand; nothing moves
  it by date.
- **Setting `usage` to `past`** stamps `auto_saved_at` and puts the row in
  自動保存. If that would exceed the limit, the request is refused unless it
  confirms; confirmed, the **oldest** slot is deleted in the same transaction.
  It is never silent: the refusal names what would go, and the caller either
  saves that row or confirms. See `api.md` for the exchange.
- **Setting `usage` from `past` to anything else** clears `auto_saved_at`; the
  row is 一般 again and its slot is free.
- **保存** (`kind: saved`) is allowed on 一般 and 自動保存 rows; `usage` and
  `auto_saved_at` are cleared. **取消保存** (`kind: free`) on a saved row sets
  `usage` to `unused`, unless the same request names another usage. Neither is
  ever refused by a limit — except 取消保存 straight to `past`, which enters
  the queue like any other `past`.
- **A template's kind never changes, and nothing becomes a template by
  update.** Sending `kind: template`, or any `kind` or `usage` to a template, is
  refused. A template is made by creating one.
- **`usage` on a row that is not (or is not becoming) 一般** is refused.
- **保存備註** (`archive_note`) is editable on every list and trip, whatever its
  kind; the screens show it where it matters (`frontend.md`).

Every check runs before anything is written, so a refused change leaves the row
as it was.

### Slots

**A slot is what the limit counts.** The oldest slot is ordered by its
`auto_saved_at`, then by `id`. The tie-break makes the answer deterministic:
two rows carrying the same `auto_saved_at` — written in one transaction, or by
hand — would otherwise be ordered by whatever the planner returned.

**Lists: a round-trip pair is one slot.** The two lists of a pair share a
`pair_id`; every unpaired list is its own slot. A pair takes its slot once
either half is auto-saved, and the second half joining it never needs room —
a full queue does not refuse it. The slot's time is the earliest
`auto_saved_at` of its auto-saved halves. Dropping a pair's slot deletes **only
its auto-saved halves**; a half still 使用中 is not part of the queue and is
not touched. Items go by cascade.

**Trips: one trip is one slot.** Legs go by cascade; a packing list a dropped
trip's leg linked is kept and unlinked, as on any trip delete.

Saving a row is how you rescue it, so a saved row is never offered for
dropping however old it is.

## Copying a list

A new list may be copied from any existing list, of any kind. **The definition
carries; the state resets.**

| Carries | Resets |
| --- | --- |
| `name`, `detail`, `category`, `quantity`, `unit`, `bag`, `location`, `need`, `timing`, `needs_double_check`, `notes`, `position` | `status` → `not_packed`, `quantity_packed` → `null`, `double_checked` → `false` |

Nothing arrives pre-ticked. A duplicated list with its ticks intact is how you
reach the airport certain you packed the charger.

The source list's own fields — `departure_at`, `kind`, `usage`, `leg`,
`pair_id`, `notes`, `archive_note`, `visibility` — are not copied. They
describe *that* list rather than its contents; the new list's `kind` comes from
the request, so 當作範本 is simply a create with `kind: template` and the
source as `copy_from_id`.

## Groups

A list's **group** is its items sharing one `category`; items with no category
are a group of their own. **筆記 and transport routes are grouped by the same
rule**, over `group_name` instead of `category` (see "Notes (筆記)" and
"Ordering routes and options"); the rule is written once, in
`app/services/domain/ordering.py`. **A group's items are always adjacent in
`position`**, because the sheet shows each group as one block. A group has no
row and no order column of its own: it sits where its items sit, so moving a
group is moving its items.

Every write that places an item keeps that true:

- **A new item joins the end of its group** — directly after the last item on
  the list with the same category, later items shifting down — or, for a
  category no item on the list carries, goes one past the end. That holds for
  a single create without `after_id` and for every item of a bulk create, the
  latter placed one by one in the order sent.
- **Changing an item's category moves it** to the end of its new group, by the
  same rule.
- **A reorder that would split a group is refused**, and so is one that does
  not name every item of the list exactly once.

`after_id` is the deliberate exception: it inserts directly after the named
item, whatever its category. So is a `PATCH` of `position`, which is taken as
sent.

## Status, and the count that does not set it

`status` is one of `not_packed`, `packed`, `no_need`, and **it is always set
explicitly** — by a tap on the status cell, the row menu, or a reset. Nothing
reads `quantity_packed` to set it: reaching the target quantity changes the
count and nothing else, and falling short only colours the 已打包數量 cell.

`quantity_packed` starts with no value (`null`): nobody has counted yet, which
is not the same as having counted none. Copying and 重設狀態 both clear it back
to that.

An item may be marked `packed` while short. Sometimes three of five is what you
are taking, and a status derived from the count would force you to edit the
target to say so. Over-packing is not an error either, and no constraint
forbids it.

`no_need` is why the status is not a boolean: without it a list never reads as
finished, and the items left unticked cannot say whether they are forgotten or
deliberately left behind.

## Double-checking

Two fields, not a fourth status value. `needs_double_check` marks an item as
needing verification; `double_checked` records that it happened. The state
worth seeing is **packed and still unverified** — the passport is in the bag
and nobody has looked at the expiry date — which a single mutually-exclusive
field cannot express.

**A list is finished when every item is resolved** (`packed` or `no_need`)
**and every item needing a double-check has had one.** A short count does not
hold the list open; an unverified item does.

## 重設狀態 (Resetting packing progress)

Resetting a list clears the state recorded from a packing pass, so the list may
be repacked from the start. **Definition carries; state resets**, mirroring the
copy rule.

| Unchanged | Cleared |
| --- | --- |
| `name`, `detail`, `category`, `bag`, `location`, `need`, `quantity`, `unit`, `timing`, `needs_double_check`, `notes` | `status` → `not_packed` (except `no_need`, which survives), `quantity_packed` → `null`, `double_checked` → `false` |

`no_need` is a choice about the list rather than progress through it, so it
survives the reset. `needs_double_check` is definition, not state, so it
survives too; only whether the check actually happened is cleared.

## Packing timing

Every item carries one of `whenever`, `night_before`, `day_of`, `just_before`.
**It is an attribute, not a mode.** The sheet shows it as the 打包時機 column
and offers it in that escalating order in its select and its filter, coloured
warmer the closer it is to leaving, which is the only special handling it gets.

It used to drive the layout: the list screen grouped by it and highlighted
whichever groups were "due", computed from `departure_at`. That was removed —
see `notes/decisions.md`. The escalating order in
`frontend/src/lib/timing.js` is what survives, along with `daysUntil`, which
turns a departure date into 明天出發 ("leaving tomorrow"). That still runs on the frontend
because the viewer's calendar day is the one that matters and the server's is
not necessarily the same one.

**A list without a departure date is normal, not incomplete.** It reads 未設定日期
and everything else works. A list's date is its own `departure_at`
unless a trip leg with a departure time links it; see "Departure source".

## The shelves and their order

**Every list and every trip is on exactly one shelf** — 一般 (`free` and not
`past`), 自動保存, 保存 or 範本 — because `kind` is one value and 自動保存 is
the 一般 rows whose usage is `past`. The two indexes return the four shelves as
four arrays, and the screens show them as they come rather than filtering them
again, so no row can fall between two screens.

**Every shelf but 自動保存 is newest `created_at` first, then highest `id`** —
lists and trips alike; trips are not ordered by their legs' dates. 自動保存 is
newest `auto_saved_at` first, the reverse of the order its slots are dropped in.
The leg picker orders by `created_at` too, on the client (`frontend.md`).

**There is no current trip.** Nothing picks one trip as the one being taken:
行程 opens the index, and the dashboard shows every 一般 trip and list that is
使用中 or 未來使用.

**The dashboard's order is by start, soonest first.** A trip starts at its
earliest entry `departs_at`; a list at its effective departure date (see
"Departure source"), taken as 00:00 in Asia/Taipei, so a list and a trip on the
same day compare by the trip's clock time. A row with no start goes last, and
rows that tie — every row without a start among them — keep the order they
came in (newest created first). 使用中 is not put before 未來使用. The rule is
`onDashboard` in `frontend/src/lib/kinds.js` and `on_dashboard` in
`app/services/domain/dashboard.py`, pinned to each other by
`tests/unit/test_dashboard_rule.py`; the sheet's readable tabs follow it.

## Copying a trip

A new trip may be copied from any trip, of any kind; the page offers templates
for 從範本 and every trip for 當作範本. **The definition carries; the state
resets**, as with a packing list.

| Carries | Resets |
| --- | --- |
| trip `notes` (unless the request sends its own), `round_trip`, `outbound_title`, `return_title`, `return_notes`; each leg's `from_place`, `to_place`, `transport_type`, `direction`, `ride_type`, `section`, the four `has_*` switches, `service`, `service_number`, `price`, `ticket_type`, `notes`, and its times, shifted | trip `ticket_status` → `not_bought`, `done` → `false`; each leg's `booked`, `paid`, `collected` → `false`; `booking_code`, `seat`, `packing_list_id` → null |

The name and `kind` come from the request. The source's own `kind`, `usage`,
`archive_note` and `visibility` are not copied, so a copy of a template is a
一般 trip (未使用) unless the request asks for another template.

**當作範本 keeps the dates.** The page sends the Taipei day of the source's own
first departure as `start_date`, so the shift below is zero.

**The shift.** `start_date` is a Taipei calendar day. Every timed leg moves by
the whole days between it and the Taipei day of the source's earliest
`departs_at`, so clock times and the gaps between legs survive; Taiwan keeps
no daylight saving. The shift may be negative. An untimed leg copies untimed.
**`start_date` is required only when some leg has a `departs_at`**: a source
with no legs, or only legs without one, needs none, and its times (an
`arrives_at` alone, say) copy unmoved.

**Packing lists are not carried.** A list is linked from at most one leg, so a
copy cannot share them. The create response's `unlinked_from` names each source
leg that had one, and the page tells you to link a list yourself.

## Trip entries and their types

A trip's entries (一段; `trip_leg` in the table and the API) each have a
**`transport_type`** — 高鐵 `hsr`, 火車 `train`, 捷運 `metro`, 公車 `bus`, 客運
`coach`, 開車 `car`, 腳踏車 `bike`, 走路 `walk`, 飛機 `flight`, 船 `ship`, 其他
`other` — and the type decides which fields the form shows and which booking
labels the entry carries. The table is `LEG_TYPES` in
`app/services/domain/leg_types.py`, mirrored in `frontend/src/lib/legTypes.js`
and spelled out in `tests/unit/test_leg_types.py`:

| type | fields shown (besides from/to, times, 備註, packing list) | 已訂票/已訂 · 已付款 · 已取票 | code |
| --- | --- | --- | --- |
| hsr | 車種 車號 座位 價錢 車票類型 方向 | fixed · fixed · fixed | fixed, 訂票代碼 |
| train, coach | 車種 車號 座位 價錢 車票類型 方向 | optional, on by default | optional on, 訂票代碼 |
| metro | 車種 價錢 方向 | absent | absent |
| bus | 車種 車號 價錢 方向 | absent | absent |
| car | 乘車類型 車種 車號 座位 價錢 | 已訂 optional off · 已付款 optional off · absent | optional off, 訂單編號 |
| bike | 類型 | 已訂 optional off · 已付款 optional off · absent | optional off, 訂單編號 |
| walk | — | absent | absent |
| flight, ship, other | 車種 車號 座位 價錢 車票類型 | optional, on by default | optional on, 訂票代碼 |

- **Each label, and the booking code, has a switch on the entry**:
  `has_booked`, `has_paid`, `has_collected`, `has_booking_code`. A fixed one is
  always on and has no switch on screen; an absent one is always off; an
  optional one is the entry's own choice.
- **A switch not sent takes the type's default** on create (fixed and
  optional-on are on; optional-off and absent are off), and **changing an
  entry's type resets every switch the same request does not name** to the new
  type's default. Sending `true` for an absent switch, or `false` for a fixed
  one, is refused.
- **`ride_type`** is 乘車類型 for a car (`hail` 叫車, `own_car` 自駕自己的車,
  `car_rental` 租車) and 類型 for a bike (`own_bike` 自己的, `youbike`,
  `moovo`, `bike_rental` 租車). A value sent that is not the entry's type's is
  refused.
- **Values of fields a type does not show are kept**, not cleared: a seat on an
  entry turned into a walk is still stored, and shows again if it is turned
  back. For the same reason only a `ride_type` sent is judged against the type,
  never one kept from an earlier type.
- An entry created without a type is `other`, with every switch on — and so is
  every entry that existed before types did.

**Times are optional.** An entry may have neither, either or both. When
`departs_at` is set and `arrives_at` is not, the server sets `arrives_at` to
`departs_at` — on create, and on the entry as a `PATCH` leaves it. Arriving at
the moment of departure is allowed; arriving before it is refused. Entries
read by `departs_at`, untimed ones last, then by `id`.

## 已準備完成 and 已買票 (Readiness)

A trip has a **`ticket_status`**: 未買票 `not_bought` (every new trip), 無需買票
`not_needed`, or 已買票 `bought`.

**A trip is ready** when its `ticket_status` is not `not_bought` and, on every
entry, every label the entry's type has and the entry has switched on is
ticked. A label the type lacks, or one switched off, does not count; nor does
the booking code, which is a field rather than a label. A trip with no entries
is ready once its tickets are settled. Reads carry the answer as `ready`.

**`done` is 已準備完成**, the owner's mark that the trip is ready to go, and
nothing sets it but the owner — but **only a ready trip can be marked**:
`done: true` on a trip that is not ready is refused, naming what is missing
(`The trip is not ready: tickets not bought; 2 entries have unticked labels.`).
It is judged on the trip as the request leaves it, so a body that settles the
tickets and marks the trip done together is accepted. Unmarking is always
allowed.

**A write that makes a done trip not ready clears `done` in the same
transaction**: unticking a label, switching one on, adding an entry with a
switched-on unticked label, changing an entry's type, or setting
`ticket_status` back to `not_bought`. Deleting an entry can only make a trip
readier, and never sets `done`.

`done` is independent of `kind` and `usage`: marking a trip moves it to no
other shelf and touches no 自動保存 slot, and moving a trip to 過去使用 does
not mark it. A new trip and every copy start not done and `not_bought` — both
are state, not definition, so neither carries.

## One-way and round trips

A trip is **單程** (`round_trip: false`, every new trip) or **來回**
(`round_trip: true`).

- **One-way**: the entries are one list, and `notes` is the trip's 備註. Every
  entry's `section` is null; a section sent for an entry of a one-way trip is
  stored as null.
- **Round trip**: the entries are in two sections, 去程 (`outbound`) and 回程
  (`return`), each with its own **title** and **remark** — `outbound_title`
  and `notes` (so nothing moves when the trip is switched), `return_title` and
  `return_notes`. The trip keeps its overall `name`. An entry created or moved
  without a `section` goes to 去程, and `PATCH section` moves one between the
  two.
- **Switching to round trip** puts every entry with no section in 去程.
- **Switching back to one-way is refused** while any entry is in 回程 or
  `return_title` or `return_notes` has text: they would be hidden, which reads
  as lost. Move or delete them first; clearing them in the same request counts.
  On success every `section` becomes null; `outbound_title` is kept but not
  shown.

## Ordering routes and options

**Routes, the options of a route and the notes of a route are ordered as a
whole**, the way a packing list's items are: one request names every route
(or every option, or note, of one route) once, and they take positions 0, 1,
2… in that order. An order that leaves one out, names one twice, or names one
that is not in the set — an unknown route, another route's option or note — is
refused and changes nothing. A new option or note goes last within its route.

**Routes have groups**, by `group_name`, under the rule in "Groups": the
routes sharing a group name stay adjacent, a blank name is no group, a new
route joins the end of its group, changing a route's group moves it to the end
of the new one (unless the same `PATCH` sends a `position`), and a route order
that splits a group is refused. Options and route notes have no groups.

## Notes on a route

A route has its 備註 (`notes`, one text value) and, below it, a list of
**notes**, each a title, a description and links in order.

- **A note needs a title or at least one link.** A description alone is not a
  note. This holds on create and for the note as a `PATCH` would leave it, so
  clearing the title of a note that keeps a link is fine, and clearing the
  last link of a note without a title is refused.
- **A blank title is no title**: titles are stripped, and an empty one is null.
- **A blank link is refused**, not dropped, so a caller that sent an empty
  row finds out. Links are stripped, and not checked to be URLs.
- **Changing a note's links replaces the list**, and the order sent is the
  links' order; that is how links are reordered.
- Deleting a route deletes its notes, and deleting a note its links.

## Notes (筆記)

**筆記 are free-standing notes**, each a title, a description and links in
order — a route note's shape without the route.

- **A note needs a title**: titles are stripped, and a blank one is refused.
  A description and links are optional.
- **Notes are grouped by `group_name`**, under the rule in "Groups": a blank
  group name is no group, a new note joins the end of its group, changing a
  note's group moves it to the end of the new one, and a reorder that splits a
  group, or does not name every note exactly once, is refused.
- **Links** follow the route-note rules: stripped, a blank one refused, and a
  `PATCH` of `links` replaces the list in the order sent.
- Deleting a note deletes its links.

## The next departure

A 交通 route's page marks, on each option, the next departure from now. It
looks only at today's day type — `weekday` Monday to Friday, `holiday` Saturday
and Sunday — and picks the earliest time at or after the current minute. Both
the weekday and the minute are read in Asia/Taipei, whatever zone the device is
in. With nothing left today, nothing is marked: the rule does not roll over to
tomorrow's first run. Public holidays are not modelled, so a national holiday
on a weekday reads the weekday row. The rule is `nextDeparture` in
`frontend/src/lib/departures.js`.

## Departure source

A list linked from a trip leg takes that leg's departure as its date: the
calendar day in Asia/Taipei, not the server's and not UTC's, so a 00:30 Taipei
departure is that day and not the previous one. The list's own `departure_at`
is ignored while the link exists **and the leg has a `departs_at`**, and is
used again, unchanged, once the link is gone or the leg's time is cleared. A
list no leg links, or one linked to an untimed leg, keeps its own date. Reads
report which one applied as `departure_source`.

## Common options

`label_option` rows are suggestions for the free-text `category`, `bag` and
`location` fields of an item and the `ticket_type` of a trip leg, learned from
what gets typed. An item or leg may always carry a value that is not among
them.

- **Saving an item records its `category`, `bag` and `location`**, and saving a
  leg its `ticket_type`, as options, if they are not already there.
- **Renaming an option rewrites every row using the old value** (items, or legs
  for `ticket_type`), because the row holds the text itself — a rename that
  touched only the option row would leave the screen showing both spellings.
- **Renaming onto an existing option merges**: rows are rewritten, then the
  source row is deleted. The unique constraint on (`kind`, `value`) would
  otherwise refuse the rename outright.
- **Deleting an option leaves the rows alone.** Pruning a typo out of the
  suggestions must not blank the field on an item or leg legitimately using it.

An option's `kind` scopes its uniqueness, so "day bag" can be both a category
and a bag. They are different facts.

## Need and location

`need` says why an item is on the list, and is null where the question does
not apply. `bring` is already owned and taken from the item's `location`; `buy`
has to be bought, at that location; `need` is needed with bring-or-buy not yet
decided. `location` is free text, suggested like `category` and `bag`.
