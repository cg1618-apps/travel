# Trip archive and trip templates — design

Working scaffolding: deleted when the work lands, with what is worth keeping
moved into `data-model.md`, `business-rules.md`, `api.md`, `frontend.md` and
`notes/decisions.md`.

## What the owner asked for

On This time:

1. Past trips can be **archived**, with an **optional remark**.
2. A **button** archives a trip.
3. Trips can be **範本** (templates), the way packing lists already can.

Settled in brainstorming:

- The remark is a **separate field** from the trip's existing `notes` (備註).
  `notes` stays the planning note; the remark is the after-the-fact one.
- Archiving **moves** a trip out of 其他行程 into its own section, is
  **reversible**, and does **not** make the trip read-only. It is manual only;
  nothing archives by itself.
- A trip created from a template gets its legs **shifted to a chosen start
  date**, keeping clock times and the day gaps between legs.
- Packing lists are **not** copied or linked. The new legs start unlinked, and
  the page **tells you** which template legs had a list so you can link one by
  hand.

## Data

One migration, `t3rip0000003_trip_archive_template`, parent `t2rip0000002`
(the head on `dev` when this was written — re-check at execution time).
Three columns on `trip`:

| Column | Type | Null | Default | Notes |
| --- | --- | --- | --- | --- |
| `archived` | boolean | no | `false` | Hidden from 其他行程 and never current. Reversible. |
| `archive_note` | text | yes | | 封存備註. Editable whether or not the trip is archived; kept when it is un-archived. |
| `template` | boolean | no | `false` | Offered as a starting point when creating a trip. Never current. |

`archived` and `template` are independent, like `saved` and `template` on
`packing_list`: a trip can be both, either or neither. A boolean rather than an
`archived_at` timestamp, matching the packing list's flags; nothing needs the
time.

The downgrade drops the three columns.

## Rules

### The current trip

Unchanged except that **archived trips and template trips are never current**.
They are filtered out before the existing rule runs. With every trip archived
or a template, there is no current trip and `/api/trips/current` answers 404.

### Archiving

Setting `archived` is the whole operation. It does not check that the trip's
legs are in the past — a cancelled trip can be archived too — and it locks
nothing: an archived trip and its legs stay editable through the same
endpoints. Un-archiving clears the flag and leaves `archive_note` alone.

### Copying a trip

A new trip may be copied from any existing trip; the page offers only
templates. **The definition carries; the state resets** — the same rule as
packing lists.

| Carries | Resets |
| --- | --- |
| trip `notes`; each leg's `from_place`, `to_place`, `departs_at`/`arrives_at` (shifted), `service`, `service_number`, `price`, `ticket_type`, `notes` | `booked`, `paid`, `collected` → `false`; `booking_code`, `seat`, `packing_list_id` → null |

The trip's `name` comes from the request, as when creating any trip. The
source trip's own fields — `archived`, `archive_note`, `template`,
`visibility` — are not copied.

`seat` and `booking_code` reset because they belong to one booking; the
service number carries because the same train is usually taken again, and is
one edit away when it is not.

### The date shift

`start_date` is a calendar date in Asia/Taipei. The offset is
`start_date − (Taipei calendar day of the source's earliest departs_at)`, in
whole days, and every copied leg's `departs_at` and `arrives_at` move by that
many days. Taipei has no daylight saving, so clock times are preserved
exactly; a leg that crosses midnight still does. The offset may be negative.

A source with no legs needs no `start_date` and ignores one if given.

### Packing lists are not carried

`packing_list_id` is unique across legs, so a copy cannot share the source's
lists, and copying the lists as well was declined. The response names each
source leg that had a list so the page can say so.

## API

**`PATCH /api/trips/{trip_id}`** — `TripUpdate` gains `archived`,
`archive_note` and `template`. `archived` and `template` are non-nullable.
Archive, un-archive, the remark and the template toggle are all this one call.

**`POST /api/trips`** — the body gains:

- `copy_from_id: int | null` — the trip to copy. Unknown → `404
  "Trip to copy from not found."`, checked before anything is written.
- `start_date: date | null` — required when the source has legs; missing →
  `422 "start_date is required to copy a trip with legs."`

The 201 response is the usual `TripResponse` plus
`unlinked_from: list[{from_place, to_place, packing_list_name}]` — empty for a
trip not copied, and for a copy whose source legs linked no lists. It is a
create-time field only and is not part of reads.

**`TripResponse`** gains `archived`, `archive_note` and `template`.
**`GET /api/trips`** still returns one list in the same order; the page
partitions it.

## Page (`pages/Trip.jsx`)

- The trip's ⋯ menu (today only 刪除行程) gains **封存** / **取消封存** and
  **設為範本** / **取消範本**.
- **封存** opens a dialog with an optional 封存備註 textarea and 封存 / 取消.
  取消封存 needs no dialog.
- An archived trip shows a **已封存** badge by its name and a 封存備註 cell
  under 備註. A template shows a **範本** badge. The 封存備註 cell is shown
  whenever the trip is archived or already has a remark.
- Below the trip, **其他行程** lists only trips that are neither archived nor
  templates. Two new sections follow it:
  - **範本** — template trips, each linking to its page.
  - **已封存** — archived trips, collapsed by default (`<details>`), each with
    its date range and the first line of its 封存備註.
  The no-current-trip empty state shows the same three sections, so archived
  trips stay reachable when nothing is current.
- **+ 新增行程** gains a 從範本 select (default 不使用範本). Choosing a
  template that has legs shows a required 出發日期 date input. After a copy, if
  `unlinked_from` is non-empty, the new trip's page shows a dismissible notice
  per leg: 「台北車站 → 彰化火車站」在範本中連結了「台北去彰化」，請自行連結打包清單。

## Tests

Backend (`tests/`), each refusal with a fixture that makes refusal possible:

- Migration: from-zero upgrade includes the columns; the downgrade drops them.
- PATCH sets and clears `archived`, `archive_note`, `template`; null for
  `archived` or `template` is a 422.
- Current trip: an archived trip **with a leg ahead of now**, alongside a
  non-archived trip with a later leg, is not current — and the mirror, the same
  fixture un-archived, is. The same pair for `template`. All trips archived →
  404.
- Copy: every carried field carries and every reset field resets, from a
  source whose legs have every reset field set (ticked, coded, seated, linked);
  the shift across a leg crossing Taipei midnight; a negative shift; source with
  legs and no `start_date` → 422 and no trip written; unknown source → 404 and
  no trip written; source with no legs and no date → 201; `unlinked_from` names
  exactly the linked legs; the source trip is unchanged.

Frontend (vitest): the three sections partition the trip list; the archive
dialog sends `archived` and `archive_note`; the 出發日期 input appears only for
a template with legs; the notice renders from `unlinked_from`.

## Out of scope

- Automatic archiving.
- Copying packing lists along with a trip.
- A read-only archived state.
- Any use of `visibility`.
