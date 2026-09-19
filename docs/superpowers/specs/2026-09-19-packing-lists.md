# Packing lists — design

Module 1 of the five in `docs/notes/decisions.md`, and the one the app is opened
for. This spec settles the shape; the plan that executes it is a separate
document and neither outlives the task.

**What this module is not:** trips, transport, buying, rules. A packing list
here stands alone and carries its own departure date. Module 2 introduces the
trip table and the nullable `trip_id` that attaches one.

## The thing being modelled

A packing list is a named set of items with a departure date, and there is
exactly **one** list entity. What varies is two independent flags:

- **`saved`** — exempt from the three-list cap. "Do not throw this away."
- **`template`** — offered as a starting point when creating a new list.

A list can be both, either or neither. A working list is neither; a template you
also keep the history of is both. There is no separate template entity, nothing
is copied *between* kinds, and promoting a list is a flag flip rather than a
duplication.

### There is no "always packed"

The original design had an `always` marker on items. It is **removed**. Nothing
is unconditionally packed — the phone is always packed right up until the trip
is strange enough that it isn't — so the set of things on every list is a
property of *the template chosen for this trip*, not of the item. Templates
already do this job, and two mechanisms for one job is how they drift apart.

This also removes the unanswerable question the flag created: when a new list is
seeded with "every always-item", *which* lists is that union read from, given
the old ones are deleted?

## Entities

### `packing_list`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | int PK | |
| `name` | text, not null | Single name, not the platform's `name_cn`/`name_en`/`aliases` convention — see below. |
| `departure_at` | date, **nullable** | What makes timing mean anything. Module 2 prefills it from the trip; the list's own value wins. |
| `saved` | bool, not null, default false | |
| `template` | bool, not null, default false | |
| `leg` | text, nullable | `outbound` \| `return` \| null. |
| `pair_id` | text, nullable | Shared by the two lists of a round trip. |
| `visibility` | text, not null, default `private` | `private` \| `unlisted` \| `public`. Unused today; present from the first migration because retrofitting the *checks* at every read path is the expensive part, not the column. |
| `created_at`, `updated_at` | timestamptz | |

**`pair_id` replaces `decisions.md`'s `paired_list_id`.** Two reasons, both
practical. A self-referencing pointer holds two copies of one fact and can
desync — A points at B while B points at C, and nothing complains. And the cap
below counts a pair as one slot, which is `COUNT(DISTINCT COALESCE(pair_id,
id))` against a shared key and an awkward self-join against a pointer. Pairing
stays purely navigational either way: **no logic crosses the pair.** Nothing
infers that what went out must come back, because the return genuinely differs.

### `packing_item`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | int PK | |
| `list_id` | FK → `packing_list`, **ON DELETE CASCADE** | An item has no life without its list. |
| `name` | text, not null | |
| `category` | text, nullable | Free text. |
| `quantity` | text, nullable | Free text, not an integer: "2 pairs", "enough for 5 days". Nothing does arithmetic on it, and the unit is usually the point. |
| `bag` | text, nullable | Free text. Which bag it goes in. |
| `status` | text, not null, default `not_packed` | `not_packed` \| `packed` \| `no_need`. |
| `timing` | text, not null, default `whenever` | `whenever` \| `night_before` \| `day_of` \| `just_before`. |
| `needs_double_check` | bool, not null, default false | This one needs verifying — the passport's expiry, whether the battery is charged. |
| `double_checked` | bool, not null, default false | Whether that verification has happened. Meaningless unless `needs_double_check`. |
| `notes` | text, nullable | |
| `position` | int, not null | Order within the list. |
| `created_at`, `updated_at` | timestamptz | |

**Double-check is two fields, not a fourth status value.** The case it exists
for is *packed and still unverified*: the passport is in the bag and you have
not looked at the expiry date. A single mutually-exclusive field cannot express
that, and that is the state that matters.

**Status is a triple, not a boolean.** Without `no_need` a list never reads as
finished, and the items left unticked cannot say whether they are forgotten or
deliberately left behind — which is the distinction you are scanning for at the
door.

**Enumerated values are text with a CHECK constraint, not a PostgreSQL enum
type.** Adding a value to a PG enum inside a reversible Alembic revision is
disproportionate ceremony for a four-value list that will grow.

### `label_option`

The common options behind the free-text fields.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | int PK | |
| `kind` | text, not null | `category` \| `bag`. |
| `value` | text, not null | |
| `position` | int, not null | |
| unique | (`kind`, `value`) | |

**Learned as you type, and prunable.** Saving an item upserts its `category` and
`bag` values here, so autocomplete works from the first list without anything
being set up first. A small maintenance screen renames, reorders, merges and
deletes them — a rename or merge rewrites the matching item values, since the
item holds text and not a reference. Nothing is ever forced to come from this
list: an item may carry a value that is not in it.

## The cap of three

Only lists that are **neither `saved` nor `template`** count. **A round-trip
pair occupies one slot**, so three round trips always fit — the pair is how a
trip is actually thought about, and charging it two slots would punish the round
trip for being modelled honestly.

Creating a fourth slot evicts the oldest, **and eviction deletes** — both lists
of a pair, and their items by cascade. It is not silent: the create call refuses
with a description of exactly what would be destroyed, and the client either
saves that list first or confirms.

```
POST /api/packing-lists                       -> 409, naming the slot that would be evicted
POST /api/packing-lists  {evict_confirmed}    -> 201, oldest slot deleted
```

**The refusal test needs three lists to exist before it can bite.** A cap
asserted against a fresh database passes because there was nothing to evict —
green on day one, green through the change that breaks it. The fixture that
creates the three is load-bearing and looks like decoration, so the test says so
in words, and asserts the mirror case (two lists → 201, nothing deleted) with
the same fixture.

## Copying

A new list may be created from any existing list — recent, saved or template
alike. **The definition carries and the state resets.**

| Carries | Resets |
| --- | --- |
| name, category, quantity, bag, timing, `needs_double_check`, notes, position | `status` → `not_packed`, `double_checked` → false |

Nothing arrives pre-ticked. A duplicated list with its ticks intact is how you
reach the airport certain you packed the charger.

The list's own `departure_at`, `saved`, `template`, `leg`, `pair_id` and
`visibility` are not copied — they describe *that* list, not its contents.

## The screens

**The list screen groups by timing, and opens on what is due now.** This is what
the `timing` field is for; a filter over a category-grouped list would leave the
app unable to answer "what do I do tonight", which is the question actually
being asked the evening before a flight.

Due-now is computed from `departure_at`:

| Group | Due when |
| --- | --- |
| `whenever` | always |
| `night_before` | departure is tomorrow or sooner |
| `day_of` | departure is today or past |
| `just_before` | departure is today or past (rendered last) |

With no `departure_at`, nothing is due: the four groups render in fixed order and
none is highlighted. Category and bag are secondary — a grouping toggle and a
filter on the same screen, not a second page.

**A list is finished when every item is resolved** — `packed` or `no_need` —
**and every item that needs a double-check has had one.** Packed-but-unverified
keeps the list open, which is the whole point of the second field.

**Mobile first.** This screen is used standing over an open suitcase holding a
phone. Tap targets and one-thumb status cycling matter more here than anywhere
else in the platform.

## Deliberate omissions

- **No item library.** Items are rows on a list, typed in. A catalogue to
  maintain is bookkeeping demanded before the app is useful, which this app has
  already rejected once.
- **Single `name`, not `name_cn`/`name_en`/`aliases`.** The platform convention
  exists for library entities that other people's data flows into — an
  ingredient, a film, an artist. A packing item is a line typed at midnight; a
  second language field and an aliases array on each one has no reader. This is
  a deliberate deviation and belongs in `decisions.md` when the module lands.
- **No weight limits, and bags are not entities.** `bag` is a label. A bag with
  a weight allowance is a real idea and can have a table when it is wanted.
- **No `/s/...` routes and no share tokens.** The prefix and the `visibility`
  column are reserved; sharing is later work and lands with its refusal tests.
- **No trips**, per the top of this document.

## Deferred, with the field already in place

- **Manual reordering.** `position` exists and is respected; drag-to-reorder is
  UI work that can follow.
- **Bulk operations** — mark a whole timing group packed, move a category to
  another bag.
