# Business rules

Last verified: 2026-09-19

**What this is for.** The rules that are not visible in the schema — what fills
the three-list cap, what eviction destroys, what a copy carries, and when an
item is due. Column-level facts live in `data-model.md`; why a rule is shaped
this way lives in `notes/decisions.md`.

These live in `app/services/domain/packing.py`, not in the routers. A router
owns wiring and status codes; a rule reimplemented in a second endpoint is a
rule with two answers.

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
| `name`, `category`, `quantity`, `unit`, `bag`, `timing`, `needs_double_check`, `notes`, `position` | `status` → `not_packed`, `quantity_packed` → 0, `double_checked` → `false` |

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

## Packing timing

Every item carries one of `whenever`, `night_before`, `day_of`, `just_before`,
and the list screen groups by it. Which groups are *due* is computed from the
list's `departure_at`:

| Group | Due when |
| --- | --- |
| `whenever` | always |
| `night_before` | departure is tomorrow or sooner |
| `day_of` | departure is today or past |
| `just_before` | departure is today or past, and rendered last |

**With no `departure_at`, nothing is due.** The four groups render in their
fixed order and none is highlighted. A list without a departure date is normal,
not incomplete.

This is computed on the frontend, in `frontend/src/lib/timing.js`, because the
viewer's calendar day is the one that matters and the server's is not
necessarily the same one.

## Common options

`label_option` rows are suggestions for the free-text `category` and `bag`
fields, learned from what gets typed. An item may always carry a value that is
not among them.

- **Saving an item records its `category` and `bag`** as options, if they are
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
