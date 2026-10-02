# Business rules

Last verified: 2026-10-01

**What this is for.** The rules that are not visible in the schema — what kind
a list or trip is and how it moves between kinds, what fills 自動保存 and what
dropping a slot destroys, what a copy carries, and how the status and check
fields relate. Column-level facts live in `data-model.md`; why a rule is shaped
this way lives in `notes/decisions.md`.

These live in `app/services/domain/`, not in the routers: kinds, usage and the
自動保存 queue in `auto_save.py`, the copy and reset rules in `packing.py`, the
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
| `name`, `detail`, `category`, `quantity`, `unit`, `bag`, `location`, `need`, `timing`, `needs_double_check`, `notes`, `position` | `status` → `not_packed`, `quantity_packed` → 0, `double_checked` → `false` |

Nothing arrives pre-ticked. A duplicated list with its ticks intact is how you
reach the airport certain you packed the charger.

The source list's own fields — `departure_at`, `kind`, `usage`, `leg`,
`pair_id`, `notes`, `archive_note`, `visibility` — are not copied. They
describe *that* list rather than its contents; the new list's `kind` comes from
the request, so 當作範本 is simply a create with `kind: template` and the
source as `copy_from_id`.

## Status, and the count that does not set it

`status` is one of `not_packed`, `packed`, `no_need`, and **it is always set
explicitly** — by a tap on the status cell, the row menu, or a reset. Nothing
reads `quantity_packed` to set it: reaching the target quantity changes the
count and nothing else, and falling short only colours the 已打包數量 cell.

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
| `name`, `detail`, `category`, `bag`, `location`, `need`, `quantity`, `unit`, `timing`, `needs_double_check`, `notes` | `status` → `not_packed` (except `no_need`, which survives), `quantity_packed` → 0, `double_checked` → `false` |

`no_need` is a choice about the list rather than progress through it, so it
survives the reset. `needs_double_check` is definition, not state, so it
survives too; only whether the check actually happened is cleared.

## Packing timing

Every item carries one of `whenever`, `night_before`, `day_of`, `just_before`.
**It is an attribute, not a mode.** The sheet shows it as the 打包時機 column
and sorts by it in that escalating order rather than alphabetically, which is the
only special handling it gets.

It used to drive the layout: the list screen grouped by it and highlighted
whichever groups were "due", computed from `departure_at`. That was removed —
see `notes/decisions.md`. The escalating order in
`frontend/src/lib/timing.js` is what survives, along with `daysUntil`, which
turns a departure date into 明天出發 ("leaving tomorrow"). That still runs on the frontend
because the viewer's calendar day is the one that matters and the server's is
not necessarily the same one.

**A list without a departure date is normal, not incomplete.** It reads 未設定日期
and everything else works. A list's date is its own `departure_at`
unless a trip leg links it; see "Departure source".

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
行程 opens the index, and the dashboard shows every 一般 trip that is 使用中 or
未來使用, 使用中 first.

## Copying a trip

A new trip may be copied from any trip, of any kind; the page offers templates
for 從範本 and every trip for 當作範本. **The definition carries; the state
resets**, as with a packing list.

| Carries | Resets |
| --- | --- |
| trip `notes` (unless the request sends its own); each leg's `from_place`, `to_place`, `service`, `service_number`, `price`, `ticket_type`, `notes`, and its times, shifted | `booked`, `paid`, `collected` → `false`; `booking_code`, `seat`, `packing_list_id` → null |

The name and `kind` come from the request. The source's own `kind`, `usage`,
`archive_note` and `visibility` are not copied, so a copy of a template is a
一般 trip (未使用) unless the request asks for another template.

**當作範本 keeps the dates.** The page sends the Taipei day of the source's own
first departure as `start_date`, so the shift below is zero.

**The shift.** `start_date` is a Taipei calendar day. Every leg moves by the
whole days between it and the Taipei day of the source's earliest departure,
so clock times and the gaps between legs survive; Taiwan keeps no daylight
saving. The shift may be negative. A source with no legs needs no date.

**Packing lists are not carried.** A list is linked from at most one leg, so a
copy cannot share them. The create response's `unlinked_from` names each source
leg that had one, and the page tells you to link a list yourself.

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
is ignored while the link exists and is used again, unchanged, once it is gone.
A list no leg links keeps its own date. Reads report which one applied as
`departure_source`.

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
