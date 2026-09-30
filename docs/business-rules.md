# Business rules

Last verified: 2026-09-30

**What this is for.** The rules that are not visible in the schema — what fills
the three-list cap, what eviction destroys, what a copy carries, and how the
status and check fields relate. Column-level facts live in `data-model.md`; why a rule is shaped
this way lives in `notes/decisions.md`.

These live in `app/services/domain/`, not in the routers: the cap, copy and
reset rules in `packing.py`, the common-options rules in `labels.py` and the
current-trip rule in `trip.py`. The sheet importer is `app/services/sheet_import/`.
A router owns wiring and status codes; a rule reimplemented in a second endpoint
is a rule with two answers.

## The three-list cap

**Three working lists at a time.** A list counts toward the cap when it is
**neither `saved` nor a `template`** — the two flags are independent, so a list
with either one set is exempt, and a list with both is exempt once.

**A round-trip pair occupies one slot.** The two lists of a pair share a
`pair_id`; every unpaired list is its own slot. Three round trips therefore
still fit, because a pair is how a trip is actually thought about and charging
it two slots would punish the round trip for being modelled honestly.

**Eviction destroys.** Creating a fourth slot removes the oldest — both lists
of a pair, and their items by cascade. It is not silent: the create call
refuses first, naming what would go, and the caller either saves that list or
confirms. See `api.md` for the exchange.

**The oldest slot is ordered by `created_at`, then by `id`.** The tie-break is
load-bearing, not defensive: `created_at` defaults to `now()`, which in
PostgreSQL is the *transaction's* start time, so lists created in one
transaction share a timestamp exactly.

Saving a list is how you rescue it from the cap, so a saved list is never
offered for eviction however old it is.

## Copying a list

A new list may be copied from any existing list — recent, saved or template
alike. **The definition carries; the state resets.**

| Carries | Resets |
| --- | --- |
| `name`, `detail`, `category`, `quantity`, `unit`, `bag`, `location`, `need`, `timing`, `needs_double_check`, `notes`, `position` | `status` → `not_packed`, `quantity_packed` → 0, `double_checked` → `false` |

Nothing arrives pre-ticked. A duplicated list with its ticks intact is how you
reach the airport certain you packed the charger.

The source list's own fields — `departure_at`, `saved`, `template`, `leg`,
`pair_id`, `visibility` — are not copied. They describe *that* list rather than
its contents, and a template copied with `template` still set is simply a
second template.

## Status, and the count that does not set it

`status` is one of `not_packed`, `packed`, `no_need`, and **it is always set
explicitly**. Reaching the target quantity offers to flip it; it never flips on
its own.

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
**It is an attribute, not a mode.** The sheet shows it as the `When` column and
sorts by it in that escalating order rather than alphabetically, which is the
only special handling it gets.

It used to drive the layout: the list screen grouped by it and highlighted
whichever groups were "due", computed from `departure_at`. That was removed —
see `notes/decisions.md`. The escalating order in
`frontend/src/lib/timing.js` is what survives, along with `daysUntil`, which
turns a departure date into "leaving tomorrow". That still runs on the frontend
because the viewer's calendar day is the one that matters and the server's is
not necessarily the same one.

**A list without a departure date is normal, not incomplete.** It reads "No
date set" and everything else works. A list's date is its own `departure_at`
unless a trip leg links it; see "Departure source".

## The current trip

The trip with the soonest leg still ahead of now is current. With nothing
ahead, the trip whose legs ended most recently is. Ties go to the newer trip
(the higher id), and a trip with no legs is never current. With no trips, or
only leg-less ones, there is no current trip.

The rule looks at the soonest *future* leg, so it can switch trips mid-journey:
while one trip's leg is under way, a trip with a leg still ahead is current. That
is accepted; see `notes/decisions.md`.

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
what gets typed. An item may always carry a value that is
not among them.

- **Saving an item records its `category`, `bag` and `location`** as options, if they are
  not already there.
- **Renaming an option rewrites every item using the old value**, because the
  item holds the text itself — a rename that touched only the option row would
  leave the screen showing both spellings.
- **Renaming onto an existing option merges**: items are rewritten, then the
  source row is deleted. The unique constraint on (`kind`, `value`) would
  otherwise refuse the rename outright.
- **Deleting an option leaves the items alone.** Pruning a typo out of the
  suggestions must not blank the field on an item legitimately using it.

An option's `kind` scopes its uniqueness, so "day bag" can be both a category
and a bag. They are different facts.

## Need and location

`need` says why an item is on the list, and is null where the question does
not apply. `bring` is already owned and taken from the item's `location`; `buy`
has to be bought, at that location; `need` is needed with bring-or-buy not yet
decided. `location` is free text, suggested like `category` and `bag`.
