# Kinds and usage status for lists and trips — design

Working scaffolding: deleted when this work lands, with what survives moved
into `business-rules.md`, `api.md`, `data-model.md`, `frontend.md` and
`notes/decisions.md`.

## Two departures from the chat, for review

1. **A list (or trip) that is today both saved and a template becomes a 範本
   only**, not a 範本 plus a 保存 copy. Templates have no cap and are never
   dropped, so nothing is lost; a copy would mean duplicating items inside a
   migration for a set that is probably empty.
2. **當作範本 on a trip copies its legs on the same dates.** The client sends
   the source's own first day as `start_date`, so the existing copy rule is
   reused unchanged.

## What this replaces

- The packing-list **three-slot cap** and its eviction on create/un-save.
- `packing_list.saved`, `packing_list.template`, `trip.archived`,
  `trip.template` — four booleans that allowed combinations the new model
  forbids.
- The date-based **current trip** rule.
- The words 封存 / 已封存 / 封存備註 and the 範本 checkbox.

## The model

Lists and trips share one model.

| Kind (`kind`) | 中文 | Made by | `usage` | Limit |
| --- | --- | --- | --- | --- |
| `template` | 範本 | Create as 範本 (blank or copied), or 當作範本 on any list/trip, which **copies** | `null` | none |
| `saved` | 保存 | 保存 on a 一般 or 自動保存 item, which **moves** it | `null` | none |
| `free` | 一般 | The ordinary create button | `in_use` 使用中 · `upcoming` 未來使用 · `unused` 未使用 | none |
| `free` + `past` | 自動保存 | Setting a 一般 item to `past` 過去使用 | `past` | lists 5 slots, trips 10 |

**自動保存 is not a stored kind.** It is `kind = 'free' AND usage = 'past'`,
so "a free item marked 過去使用 is auto-saved" is true by construction rather
than kept in step by code.

Columns, on both `packing_list` and `trip`:

| Column | Type | Rule |
| --- | --- | --- |
| `kind` | string, not null, default `free` | `template` / `saved` / `free` (check constraint) |
| `usage` | string, nullable | not null **iff** `kind = 'free'`; one of the four values (check constraints) |
| `auto_saved_at` | timestamptz, nullable | not null **iff** `usage = 'past'` (check constraint); the queue order |
| `notes` | text, nullable | 備註 — lists gain it; trips have it |
| `archive_note` | text, nullable | 保存備註 — lists gain it; trips keep theirs |

`saved`, `template` (both tables) and `archived` (trip) are dropped.

## The rules

- **A new 一般 item starts `unused`.** Usage changes only by hand.
- **Setting `usage = past`** stamps `auto_saved_at = now()` and puts the item
  in 自動保存. If that would exceed the limit, the request is refused with
  `409` unless `evict_confirmed` is sent; confirmed, the **oldest** auto-saved
  slot is deleted in the same transaction.
- **Setting `usage` from `past` to anything else** clears `auto_saved_at`; the
  item is 一般 again and its slot is free.
- **The oldest slot** is ordered by `auto_saved_at`, then `id` (the tie-break
  is load-bearing, as it is for the cap today: `now()` is the transaction's
  start).
- **List slots: a round-trip pair is one slot.** Slot key is
  `coalesce(pair_id, id)` over auto-saved lists only. A pair takes its slot
  once either half is auto-saved; its slot time is the earliest
  `auto_saved_at` of its auto-saved halves. Dropping a slot deletes **only the
  auto-saved halves** — a half still 使用中 is not touched. Items go by
  cascade.
- **Trip slots: one trip is one slot.** Legs go by cascade; a linked packing
  list is kept and unlinked, as on any trip delete.
- **保存** (`kind: saved`) is allowed on 一般 and 自動保存 items: `usage` and
  `auto_saved_at` are cleared. **取消保存** (`kind: free`) on a saved item sets
  `usage = unused`. Neither can be refused by a limit.
- **A template's kind never changes**, and nothing becomes a template by
  `PATCH`: `kind: template` in a `PATCH`, or any `kind` on a template, is a
  `422`. A template is made by creating one.
- **`usage` on a non-free item** in a `PATCH` is a `422`.
- **保存備註** is editable on every list and trip; the screens show it where it
  matters (below).

### The current trip

`/api/trips/current` picks, among 一般 trips:

1. those with `usage = in_use`, else
2. those with `usage = upcoming`;

and within the group, the trip whose soonest leg **still ahead of now** is
earliest; trips with no leg ahead come after, newest (highest id) first. No
trip in either group is `404 No current trip.` A trip with no legs **can** be
current now — the status, not the legs, makes it current.

## API

Both indexes get the same shape.

`GET /api/packing-lists` and `GET /api/trips` return:

| Field | Contents |
| --- | --- |
| `free` | 一般 items not `past`, each with `usage` |
| `auto_saved` | 自動保存 items, newest `auto_saved_at` first |
| `saved` | 保存 items |
| `templates` | 範本 items |
| `evict_next` | The slot the next `past` would delete, or `[]` when there is room |

`GET /api/trips` changes from a bare array to this object; its one caller
(`Trip.jsx`) moves with it. Trips are still nested with their legs.

Every list and trip read carries `kind`, `usage`, `auto_saved_at`, `notes`,
`archive_note`. `saved`, `template` and `archived` are gone from requests and
responses.

**Create** (`POST /api/packing-lists`, `POST /api/trips`) accepts `kind`:
`free` (default) or `template`. `saved` is a `422` — saving is a move.
`copy_from_id` works as today from any kind; with `kind: template` it is
當作範本. No create can be refused by a limit, so `evict_confirmed` leaves
create.

**Update** (`PATCH`) accepts `kind` (`saved`/`free`), `usage`, `notes`,
`archive_note`, `evict_confirmed`; `kind` and `usage` refuse `null`. A
`PATCH` that sends `usage: past` and would overflow answers `409` with a
plain English `detail`; the names come from `evict_next`.

**Bulk delete**: `POST /api/trips/bulk-delete` `{ "ids": [..] }` → `204`.
Every id must exist or the answer is `404` and nothing is deleted. Packing
lists get no bulk endpoint (自動保存 holds at most five slots).

## Screens

All strings Traditional Chinese; the stored values above map to labels in
`lib/labels.js` (`KIND_LABELS`, `USAGE_LABELS`) and nowhere else.

### `/lists` 打包清單

- **+ 新增清單** gains a 一般 / 範本 choice; 從哪份清單複製項目 offers every
  list.
- Sections, in order:
  - **一般** — 狀態 select, 保存 checkbox, 當作範本 button.
  - **自動保存（n / 5）** — the same row; 狀態 reads 過去使用, and changing it
    returns the list to 一般. First line of 保存備註 under the name.
  - **保存** — 保存 checkbox, 當作範本; first line of 保存備註.
  - **範本** — no checkbox.
- **當作範本** creates `{name}（範本）` with the items copied and shows a
  notice linking to it.
- **過去使用 when full** opens `EvictDialog` naming `evict_next`, with 保存
  that list instead as the first option; confirming retries with
  `evict_confirmed`.
- **Unticking 保存** opens `ConfirmDialog`: 取消保存後會回到一般清單（未使用）。
- The **list page header** carries the same 狀態, 保存 and 當作範本 controls,
  a **備註** cell, and a **保存備註** cell when the list is saved, auto-saved
  or already has one.

### 行程 (`/trip`, `/trips/:id`)

- Header: a **狀態** select on 一般 and 自動保存 trips; a 範本 / 保存 / 自動保存
  badge.
- ⋯ menu: **保存** / **取消保存** (asks first), **當作範本**, **刪除行程**.
  封存 and 設為範本 are gone, and with them the archive dialog.
- **保存備註** replaces 封存備註; shown on saved and auto-saved trips, and on
  any trip that already has one.
- **+ 新增行程** gains 一般 / 範本; 從範本 stays.
- Sections below the trip: **一般**, **保存**, **範本**, and a link
  **自動保存的行程（n / 10）→**. 已封存 is gone.
- A change that moves the trip on `/trip` out of being current (保存, or a
  usage change) moves the page to `/trips/{id}`, as 封存 does today.

### 自動保存的行程 (`/trips/auto-saved`)

- Every auto-saved trip, newest first, with its date range and the first line
  of 保存備註.
- **刪除模式** toggles a checkbox on every row, **全選**, and **刪除所選（n）**,
  which opens one `ConfirmDialog` naming every trip, then calls bulk delete.
- Reached from the 行程 page, not the nav bar.

### Dashboard `/`

Two sections, **清單** and **行程**: 一般 items with `usage` `in_use` or
`upcoming`, 使用中 first, each with a status badge. The 目前 badge goes. Nothing
to add or edit.

### Deleting

Single deletes keep their existing confirmation; 刪除模式 confirms once for
the selection.

## Migration

One Alembic revision for both tables.

| Today | Becomes |
| --- | --- |
| list `template` (with or without `saved`) | `kind = template` |
| list `saved` only | `kind = saved` |
| list neither | `kind = free`, `usage = unused` |
| trip `template` (with or without `archived`) | `kind = template` |
| trip `archived` only | `kind = saved`; `archive_note` kept |
| trip neither | `kind = free`, `usage = unused` |

**Downgrade** restores the booleans from `kind` (`saved` → `saved` /
`archived`, `template` → `template`) and drops `usage`, `auto_saved_at` and
the list's `notes` / `archive_note`. Usage and list remarks are lost; the
deploy notes in `deployment-selfhost.md` say so.

## The importer

`scripts/import_sheet.py` creates lists and one trip; they become `kind = free`,
`usage = unused`. Nothing else in it changes.

## Testing

- **Refusal tests have something to refuse.** Every limit test fills
  自動保存 to the limit first (five list slots, ten trips) and asserts the
  mirror case — one under the limit is accepted — with the same fixture.
- Slots: a pair counts once; dropping a pair spares a half still 使用中;
  `auto_saved_at` ties break on `id`.
- Kind transitions: every allowed move, and every `422` (to template, from
  template, `usage` on non-free, `saved` on create, null `kind`/`usage`).
- Current trip: 使用中 beats 未來使用; within a group the soonest leg ahead
  wins; no 一般 trip in either group is `404`.
- Bulk delete: all or nothing on a missing id.
- Migration: the from-zero test runs the chain; a data test seeds each row
  of the mapping table at the previous head and checks it after upgrade and
  after downgrade.
- Frontend: `lib/` helpers for grouping, labels and dashboard filtering are
  pure and tested; `labels.test.js` covers the two new vocabularies.
