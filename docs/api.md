# API

Last verified: 2026-10-01

**What this is for.** Every HTTP endpoint this application serves. The
authority is FastAPI's own route table — if a row here and the dump disagree,
the dump wins and this page is wrong:

```bash
venv/Scripts/python.exe -c "from app.main import app; [print(r.methods, r.path) for r in app.routes]"
```

The rules behind these endpoints — kinds, usage and the 自動保存 queue, what a copy carries —
are in `business-rules.md`. The tables they read and write are in
`data-model.md`.

## Authentication

**There is none, and that is deliberate.** `travel` is
`exposure: cloudflare-access` in the platform's registry, so Cloudflare
authenticates before a request reaches the box. There is no login page, no
session, no password and no auth code in this application: one user, one
person's data.

Every endpoint below is therefore unauthenticated *as far as this codebase is
concerned*. Whether the gate in front of it is actually enforcing is a
question only a probe from the open internet answers, and the platform's
`bin/check-exposure` is what asks it.

## Conventions shared by many routers

| Convention | Where | Behaviour |
| --- | --- | --- |
| Error shape | every endpoint | A refusal a router raises is `{"detail": "a sentence"}`, a plain English string. A `422` from schema validation — a missing or empty required field, an unknown enum value, a time with no offset, an explicit `null` on a required field — is FastAPI's own shape, where `detail` is a list of `{loc, msg, type}` objects. The frontend's `fetchJson` flattens that list into one message (the `msg`s joined), but no screen renders either kind: pages branch on the status code and show their own zh-TW text (`frontend.md`). Anything a caller needs to *act* on arrives as data on a normal response, not inside an error. |
| Create | every `POST` | `201` with the created object. |
| Update | every `PATCH` | `200` with the updated object. Only the fields present in the body change; omitting a field leaves it alone. |
| Delete | every `DELETE` | `204` with no body. |
| Unknown id | every `{id}` path | `404` with a generic message. |
| Unknown enum value | any field typed as one | `422` from the schema, before the database's `CHECK` constraint is reached. The constraint is the backstop, not the error message. |
| The 自動保存 queue | `PATCH /api/packing-lists/{id}`, `PATCH /api/trips/{id}` | `409` when setting `usage: past` would destroy the oldest slot, naming it. Repeat the request with `evict_confirmed: true` to proceed. See below. |

## Table of contents

- [Health — `/api/health`](#health--apihealth)
- [Packing lists — `/api/packing-lists`](#packing-lists--apipacking-lists)
- [Packing items — `/api/packing-items`](#packing-items--apipacking-items)
- [Common options — `/api/label-options`](#common-options--apilabel-options)
- [Transport — `/api/transport-routes`](#transport--apitransport-routes)
- [Trips — `/api/trips`](#trips--apitrips)

## Health — `/api/health`

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/api/health` | none | `200` only when the database is reachable **and** the revision it is stamped with matches the head the running code ships. `503` otherwise. |

The revision comparison is the part nothing else on the box would notice: after
a failed migration-bearing deploy the database holds the new revision while the
image has rolled back to code that has never heard of it, and pages still
serve.

## Packing lists — `/api/packing-lists`

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/api/packing-lists` | none | The four shelves, plus `evict_next`. |
| `POST` | `/api/packing-lists` | none | Create a list, optionally copying another's items. Never refused by a limit. |
| `GET` | `/api/packing-lists/{id}` | none | One list with its items, in `position` order. |
| `PATCH` | `/api/packing-lists/{id}` | none | Change any of `name`, `departure_at`, `kind`, `usage`, `notes`, `archive_note`, `leg`, `pair_id`. `409` if `usage: past` would evict. |
| `POST` | `/api/packing-lists/{id}/reset` | none | Reset the list's packing progress. Unpacks `packed` items, clears `quantity_packed` and `double_checked`, but leaves `no_need` and `needs_double_check` definition alone. |
| `DELETE` | `/api/packing-lists/{id}` | none | `204`. Items go with it. |

Every read of a list carries `kind`, `usage`, `auto_saved_at`, `notes`,
`archive_note` and `created_at` (the vocabulary is in `business-rules.md`,
"Kinds, usage and 自動保存"). Every read also carries `departure_at` as the
**effective** date, and `departure_source`, `"list"` or `"trip_leg"`. While a
trip leg links the list, `departure_at` is that leg's Asia/Taipei calendar day
and `departure_source` is `trip_leg`; otherwise both are the list's own. A
`PATCH` of `departure_at` writes the list's own date, which stays hidden behind
the leg until the link is removed.

**A `PATCH` cannot null a required field.** `name`, `kind` and `usage` answer
`422` when sent as `null`; `departure_at`, `leg`, `pair_id`, `notes` and
`archive_note` accept it and clear. `evict_confirmed` is not a column but a
plain boolean, and refuses `null` the same way.

### The index

`GET /api/packing-lists` returns five fields, all arrays of list summaries.
Every list is in exactly one of the first four:

| Field | What is in it |
| --- | --- |
| `free` | 一般 lists that are not `past`, each with its `usage`. |
| `auto_saved` | 自動保存 lists (`kind` `free`, `usage` `past`), newest `auto_saved_at` first. |
| `saved` | Lists with `kind` `saved`. |
| `templates` | Lists with `kind` `template`. |
| `evict_next` | The slot the next `usage: past` would destroy, or `[]` when there is room. Both auto-saved halves of a round-trip pair. |

Every array but `auto_saved` is newest `created_at` first, then `id`.

Each summary carries `item_count` and `settled_count` — how many items the list
has, and how many are `packed` or `no_need`. The index renders them as a
fraction; sending the items themselves so the client could count them would be
a page-sized payload for one number. A list's own `GET` returns the items and
omits the counts.

`evict_next` exists because the `409` below cannot carry it. The refusal's
`detail` is a plain string, so the ids a confirmation dialog needs to offer
"save it instead" arrive here instead — on a response the screen has already
loaded, costing no extra request.

### Creating

`POST /api/packing-lists` takes the list's own fields plus two extras:

| Field | Meaning |
| --- | --- |
| `kind` | `free` (the default) or `template`. `saved` is a `422`: saving is a move, made by `PATCH`. |
| `copy_from_id` | Copy this list's items. Any list will do, of any kind. Definition carries, state resets. With `kind: template` this is 當作範本. |

A `free` list starts `usage: unused`. **No create can be refused by a limit**,
so `evict_confirmed` is not a create field. An unknown `copy_from_id` is a
`404` and nothing is written.

### Changing kind and usage, and the refusal

`PATCH` accepts `kind` (`saved` or `free`) and `usage` (`in_use`, `upcoming`,
`unused`, `past`). `kind: template` is refused by the schema, and a template's
`kind` or `usage` and a `usage` on a saved list answer `422` with a plain
`detail`; a list becomes a template only by being created as one.

Setting `usage: past` on a full queue is the one refusal, and it is two steps:

```
PATCH /api/packing-lists/7 {"usage": "past"}
  -> 409 {"detail": "Auto-save already holds 5 lists. Marking this one past would
                     delete \"Kyoto\", the oldest. Save it first if you want to
                     keep it, or confirm to replace it."}

PATCH /api/packing-lists/7 {"usage": "past", "evict_confirmed": true}
  -> 200
```

The number in the message is the queue's limit (`AUTO_SAVE_LIMIT`: 5 list
slots, 10 trips); the names come from `evict_next`. **A refused `PATCH` changes
nothing**: every check runs before anything is written.

**Saving is never refused.** `kind: saved` clears `usage`, so it frees a slot
rather than taking one, and `kind: free` on a saved list sets `usage: unused`.
The second half of a pair whose first half is already auto-saved joins that
slot and is not refused either.

## Packing items — `/api/packing-items`

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `POST` | `/api/packing-lists/{list_id}/items` | none | Add an item. It lands at the end of **that** list, or directly after `after_id` on that list, shifting later items. |
| `PATCH` | `/api/packing-items/{id}` | none | Change any field. `null` clears a nullable one. |
| `DELETE` | `/api/packing-items/{id}` | none | `204`. |

An item is created under the list that owns it and addressed on its own
afterwards, which is why the two path shapes differ.

Beyond the name, an item's text fields are `detail`, `category`, `bag` and
`location`; `need` is one of `need`, `bring`, `buy` or `null`, and any other
value is a `422`.

`position` is assigned by the server. By default, it lands one past the end of
that list. Pass `after_id` — the id of an item on **that same list** — to
insert directly after it instead, shifting every later item down by one. An
`after_id` naming no item on that list is a `404`. Positions are counted **per
list rather than globally** — a shared counter would leave a new list's first
item at position 400, sorting correctly by accident until something compared
positions across lists.

### What does not happen automatically

| Not done | Why |
| --- | --- |
| Reaching `quantity` does not set `status` | The count suggests; the caller decides. An item may be `packed` while short, because sometimes three of five is what you are taking, and a derived status would force you to edit the target to say so. |
| `quantity_packed` above `quantity` is not refused | Over-packing is a real state, not an error. |
| `double_checked` and `status` do not drive each other | *Packed and still unverified* is the state the second field exists for. |

Sending `null` clears a nullable field. The router uses `exclude_unset`, not
`exclude_none`, so "remove this category" and "leave the category alone" are
different requests.

**A `PATCH` cannot null a required field.** `name`, `quantity_packed`,
`status`, `timing`, `needs_double_check`, `double_checked` and `position` answer
`422` when sent as `null`; nullable fields such as `notes`, `need` and
`location` accept it and clear.

## Common options — `/api/label-options`

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/api/label-options` | none | Every option, in `position` order. `?kind=category`, `?kind=bag`, `?kind=location` or `?kind=ticket_type` narrows it. |
| `PATCH` | `/api/label-options/{id}` | none | Rename or reorder. A rename rewrites the rows using it (items, or legs for `ticket_type`); renaming onto an existing value **merges**. |
| `DELETE` | `/api/label-options/{id}` | none | `204`. The rows using it are left alone. |

There is no `POST`. Options are **learned**: writing an item records its
`category`, `bag` and `location`, and writing a leg records its `ticket_type`, on
create and on any `PATCH` that changes them.

Each option carries a `usage_count` — how many rows currently hold that value
in the option's column: items for `category`, `bag` and `location`, trip legs
for `ticket_type` — so a rename screen can say what it is about to rewrite
before it does it.

**A rename can delete the row you addressed.** Renaming onto a value that
already exists merges the two: the rows are rewritten either way, then the
source row is removed, because the unique constraint on (`kind`, `value`) would
refuse the update outright. The response is the **surviving** option, not the
one named in the path — the rename succeeded, so a `404` would be a lie.

**Deleting prunes a suggestion and nothing else.** Items and legs keep the value, and
typing it again brings the option back. These rows are autocomplete, not
records.

## Transport — `/api/transport-routes`

A route owns options, and an option owns departures. Like packing items, a
child is created under its parent and addressed on its own afterwards.

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/api/transport-routes` | none | Every route by `position`, then `id`, with its options and their departures nested. |
| `POST` | `/api/transport-routes` | none | `201`. `from_place` and `to_place` are required and non-empty. |
| `GET` / `PATCH` / `DELETE` | `/api/transport-routes/{id}` | none | `404` when missing. Deleting takes the options and departures with it. |
| `POST` | `/api/transport-routes/{route_id}/options` | none | `201`. `mode` is required and non-empty. The option is appended after the route's last one. |
| `PATCH` / `DELETE` | `/api/transport-options/{id}` | none | Deleting takes the option's departures with it. |
| `POST` | `/api/transport-options/{option_id}/departures` | none | `201`. `day_type` is `weekday` or `holiday`; `time` is `HH:MM`. `irregular` defaults to `false`. |
| `PATCH` / `DELETE` | `/api/transport-departures/{id}` | none | |

**A departure is unique per option, day type and time.** Creating one that
already exists, or a `PATCH` that would make one collide, is a `409` with
`That departure already exists for this option.` The same time on the other day
type is a different departure. Departures read back ordered by `day_type` (alphabetically, so `holiday` before
`weekday`), then `time`, and `time` is serialised as `HH:MM:SS`.

**A `PATCH` cannot null a required field.** `from_place`, `to_place`, `mode`,
`advance_ticket`, `day_type`, `time`, `irregular` and `position` answer `422`
when sent as `null`; nullable fields such as `notes` accept it and clear.

## Trips — `/api/trips`

A trip owns legs. Like packing items, a leg is created under its trip and
addressed on its own afterwards.

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/api/trips` | none | The same four shelves as packing lists — `free`, `auto_saved`, `saved`, `templates` — plus `evict_next`, each trip with its legs nested. Every array but `auto_saved` is newest `created_at` first; `auto_saved` is newest `auto_saved_at` first. `evict_next` is the trip the next `usage: past` would destroy, or `[]`. |
| `POST` | `/api/trips/bulk-delete` | none | `{"ids": [..]}` → `204`. Every id must exist or the answer is `404` and nothing is deleted. Packing lists have no bulk endpoint; their queue holds at most five slots. |
| `POST` | `/api/trips` | none | `201`. `name` is required and non-empty. `kind` is `free` (the default) or `template`; `saved` is a `422`, and no create is refused by a limit. A `free` trip starts `usage: unused`. Optional `copy_from_id` copies another trip (see `business-rules.md`, "Copying a trip"): `404` `Trip to copy from not found.` for an unknown one, and `422` `start_date is required to copy a trip with legs.` when it has legs and no `start_date` (a date) was sent. Nothing is written on either refusal; a `start_date` without `copy_from_id` is ignored. The response adds `unlinked_from`, `[{from_place, to_place, packing_list_name}]`, empty unless a copied leg had a list. |
| `GET` / `PATCH` / `DELETE` | `/api/trips/{id}` | none | `404` when missing. `PATCH` takes `name`, `notes`, `archive_note`, `kind`, `usage` and `evict_confirmed`, with the same rules and the same `409` as a packing list; `name`, `kind` and `usage` refuse null with `422`. Every read carries `kind`, `usage`, `auto_saved_at`, `archive_note` and `created_at`. Deleting takes the legs with it. |
| `POST` | `/api/trips/{trip_id}/legs` | none | `201`. `from_place`, `to_place`, `departs_at` and `arrives_at` are required. |
| `PATCH` / `DELETE` | `/api/trip-legs/{id}` | none | `404` when missing. |

A leg response carries `packing_list_name`, the linked list's name or `null`.

There is no current trip: `GET /api/trips/current` does not exist, and the path
falls to `/api/trips/{trip_id}`, which answers `422` for the non-integer id.

**Times carry a zone.** `departs_at` and `arrives_at` are ISO 8601 with an
offset, for example `2026-09-24T18:06:00+08:00`; a time without one is a `422`.

**`arrives_at` must be after `departs_at`**, else `422`. On create the schema
checks it, so the `422` is FastAPI's list (its `msg` is `Value error, arrives_at
must be after departs_at`). A `PATCH` is checked by the router against the
merged values, so moving only one of the two is judged against the stored
other, and its `422` is the plain string `arrives_at must be after departs_at`.

**Linking a list.** `packing_list_id` naming no list is a `404`. A list already
linked from another leg is a `409` with `That packing list is already linked to
another leg.`; a `PATCH` that keeps the leg's own link is not a collision.
Deleting a linked list keeps the leg and clears its link.

**A leg's `ticket_type` is remembered** as a `ticket_type` label option.

**A `PATCH` cannot null a required field.** `name`, `kind` and `usage` on a trip, and `from_place`,
`to_place`, `departs_at`, `arrives_at`, `booked`, `paid` and `collected` on a
leg, answer `422` when sent as `null`; nullable fields such as `notes` accept it
and clear.
