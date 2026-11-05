# API

Last verified: 2026-11-04

**What this is for.** Every HTTP endpoint this application serves. The
authority is FastAPI's own route table — if a row here and the dump disagree,
the dump wins and this page is wrong:

```bash
venv/Scripts/python.exe -c "from app.main import app; [print(r.methods, r.path) for r in app.routes]"
```

The rules behind these endpoints — what fills 自動保存, what a copy carries —
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
| 自動保存 | `PATCH /api/packing-lists/{id}`, `PATCH /api/trips/{id}` | `409` when `usage: past` would drop the oldest 自動保存 slot, naming it. Repeat the request with `evict_confirmed: true` to proceed. See "Kinds, and the refusal". |

## Table of contents

- [Health — `/api/health`](#health--apihealth)
- [Packing lists — `/api/packing-lists`](#packing-lists--apipacking-lists)
- [Packing items — `/api/packing-items`](#packing-items--apipacking-items)
- [Common options — `/api/label-options`](#common-options--apilabel-options)
- [Transport — `/api/transport-routes`](#transport--apitransport-routes)
- [Trips — `/api/trips`](#trips--apitrips)
- [Notes — `/api/notes`](#notes--apinotes)
- [Backup — `/api/backup`](#backup--apibackup)

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
| `POST` | `/api/packing-lists` | none | Create a list — `kind` `free` (default) or `template` — optionally copying another's items. Never refused by 自動保存. |
| `GET` | `/api/packing-lists/{id}` | none | One list with its items, in `position` order. |
| `PATCH` | `/api/packing-lists/{id}` | none | Change any of `name`, `departure_at`, `kind`, `usage`, `leg`, `pair_id`, `notes`, `archive_note`. `409` if `usage: past` would drop a 自動保存 slot. |
| `POST` | `/api/packing-lists/{id}/reset` | none | Reset the list's packing progress. Unpacks `packed` items, clears `quantity_packed` to `null` and `double_checked` to `false`, but leaves `no_need` and `needs_double_check` definition alone. |
| `PUT` | `/api/packing-lists/{id}/order` | none | Set the order of the list's items. Body `{"item_ids": [..]}`; returns the list as its `GET` does. See "Ordering" below. |
| `DELETE` | `/api/packing-lists/{id}` | none | `204`. Items go with it. |

Every read of a list carries `kind`, `usage`, `auto_saved_at`, `notes`,
`archive_note` and `created_at`; `departure_at` as the **effective** date; and
`departure_source`, `"list"` or `"trip_leg"`. While a trip leg with a
`departs_at` links the list, `departure_at` is that leg's Asia/Taipei calendar
day and `departure_source` is `trip_leg`; otherwise — no link, or a leg with no
time — both are the list's own. A `PATCH` of `departure_at` writes the list's
own date, which stays hidden behind a timed leg until the link or the time is
removed.

**A `PATCH` cannot null a required field.** `name`, `kind` and `usage` answer
`422` when sent as `null`; `departure_at`, `leg`, `pair_id`, `notes` and
`archive_note` accept it and clear. `evict_confirmed` is not a column but a
plain boolean, and refuses `null` the same way.

### The index

`GET /api/packing-lists` returns five fields, all arrays of list summaries.
Every list is on exactly one of the four shelves, and every shelf but
`auto_saved` is newest `created_at` first, then highest `id`:

| Field | What is in it |
| --- | --- |
| `free` | 一般 lists that are not 過去使用, each with its `usage`. |
| `auto_saved` | 自動保存: 一般 lists whose `usage` is `past`, newest `auto_saved_at` first. |
| `saved` | Lists whose `kind` is `saved`. |
| `templates` | Lists whose `kind` is `template`. |
| `evict_next` | The slot the next `usage: past` would drop, or `[]` while there is room. Every auto-saved half of a round-trip pair. |

Each summary carries `item_count` and `settled_count` — how many items the list
has, and how many are `packed` or `no_need`. The index renders them as a
fraction; sending the items themselves so the client could count them would be
a page-sized payload for one number. A list's own `GET` returns the items and
omits the counts.

`evict_next` exists because the `409` below cannot carry it. The refusal's
`detail` is a plain string, so the ids a confirmation dialog needs to offer
"save it instead" arrive here instead — on a response the screen has already
loaded, costing no extra request.

### Kinds, and the refusal

`POST /api/packing-lists` takes the list's own fields plus:

| Field | Meaning |
| --- | --- |
| `kind` | `free` (the default; the list starts 未使用) or `template`. `saved` is a `422` from the schema: saving is a move, not a way to create. |
| `copy_from_id` | Copy this list's items. Any list will do, of any kind. Definition carries, state resets. With `kind: template` this is 當作範本. An unknown id is a `404` and nothing is written. |

A `PATCH` moves a list between kinds (`business-rules.md`, "Kinds, usage and
自動保存"):

| Body | Effect |
| --- | --- |
| `{"kind": "saved"}` | 保存. Allowed on a 一般 or 自動保存 list; clears `usage` and `auto_saved_at`. |
| `{"kind": "free"}` | 取消保存. The list is 一般 again, `usage` `unused` unless the same body names another. |
| `{"usage": ...}` | A 一般 list's 狀態. `past` puts it in 自動保存; anything else takes it out. |
| `{"kind": "template"}` | `422` from the schema. A template is made by creating one. |
| any `kind` or `usage` on a template | `422`, `A template's kind and usage cannot change.` |
| `usage` on a list that is not 一般 and not becoming one | `422`, `Only a free list or trip has a usage.` |

Only `usage: past` can be refused by the limit, and the exchange is
deliberately two steps:

```
PATCH /api/packing-lists/12 {"usage": "past"}
  -> 409 {"detail": "Auto-save already holds 5 lists. Marking this one past
                     would delete \"Kyoto\", the oldest. Save it first if you
                     want to keep it, or confirm to replace it."}

PATCH /api/packing-lists/12 {"usage": "past", "evict_confirmed": true}
  -> 200
```

The number in the `detail` is the limit itself (`AUTO_SAVE_LIMIT` in
`app/services/domain/auto_save.py`), and the names are the rows `evict_next`
lists. **A refused `PATCH` changes nothing**: every check runs before anything
is written, and the oldest slot is deleted only inside the confirmed request's
own transaction. The second half of a pair whose first half is already
auto-saved joins that slot and is never refused.

### Ordering

`PUT /api/packing-lists/{id}/order` takes `{"item_ids": [..]}` and gives the
items `position` 0, 1, 2… in that order. The answer is `200` with the list,
items in their new order, the same shape as `GET /api/packing-lists/{id}`. An
unknown list is a `404`.

The order must name **every item on the list exactly once**, and must keep
**each group together** — a group being the items sharing a `category`, with
`null` a group of its own (`business-rules.md`, "Groups"). Anything else is a
`422` whose `detail` is a plain string, and nothing is changed:

| Body | `detail` |
| --- | --- |
| an id named twice | `Item 7 appears more than once in the order.` |
| an id not on this list | `Not on this list: items 7.` |
| an item of the list left out | `The order must name every item on this list; missing items 7.` |
| one category in two separate runs | `The order splits the "衣服" group: a group's items must be adjacent.` (`the uncategorised group` for `null`) |

Moving a group is moving its items: there is no group row and no group order
column, so a group sits where its items sit.

The same whole-order rule orders 筆記 and transport routes, groups included
(by `group_name`), and the options and notes of a route, without groups — see
"Ordering" under Transport and under Notes.

## Packing items — `/api/packing-items`

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `POST` | `/api/packing-lists/{list_id}/items` | none | Add an item. It lands at the end of its group on **that** list, or directly after `after_id` on that list, shifting later items. |
| `POST` | `/api/packing-lists/{list_id}/items/bulk-create` | none | `201`. Add several items at once, all or nothing. Body `{"items": [..]}`; returns the created items in request order. |
| `PATCH` | `/api/packing-items/{id}` | none | Change any field. `null` clears a nullable one. A changed `category` moves the item to the end of its new group. |
| `DELETE` | `/api/packing-items/{id}` | none | `204`. |

An item is created under the list that owns it and addressed on its own
afterwards, which is why the two path shapes differ.

Beyond the name, an item's text fields are `detail`, `category`, `bag` and
`location`; `need` is one of `need`, `bring`, `buy` or `null`, and any other
value is a `422`.

`quantity_packed` is `null` unless sent: no value means nobody has counted,
which is not the same as `0`. An explicit `0` is kept.

`position` is assigned by the server. By default a new item **joins its
group**: it lands directly after the last item on that list with the same
`category` (`null` matching `null`), shifting every later item down by one;
when no item on the list has that category it lands one past the end. Pass
`after_id` — the id of an item on **that same list** — to insert directly
after it instead, whatever its category. An `after_id` naming no item on that
list is a `404`. Positions are counted **per list rather than globally** — a
shared counter would leave a new list's first item at position 400, sorting
correctly by accident until something compared positions across lists.

**A `PATCH` that changes `category`** moves the item by the same rule: to the
end of its new group, or one past the end of the list for a category no other
item carries. Sending the category it already has moves nothing, and a
`position` sent in the same `PATCH` wins over the move.

### Bulk create

`POST /api/packing-lists/{list_id}/items/bulk-create` takes `{"items": [..]}`,
at least one, each with the fields of a single create except `after_id`. It
answers `201` with the created items, in request order.

- **All or nothing.** The body is validated whole, so one bad item is a `422`
  and nothing is created; the rows are committed together.
- **Placed in request order**, each by the group rule above, so two new items
  of the same new category land adjacent and in the order sent.
- Labels are remembered as for a single create. An unknown list is a `404`.

### What does not happen automatically

| Not done | Why |
| --- | --- |
| Reaching `quantity` does not set `status` | The count suggests; the caller decides. An item may be `packed` while short, because sometimes three of five is what you are taking, and a derived status would force you to edit the target to say so. |
| `quantity_packed` above `quantity` is not refused | Over-packing is a real state, not an error. |
| `double_checked` and `status` do not drive each other | *Packed and still unverified* is the state the second field exists for. |

Sending `null` clears a nullable field. The router uses `exclude_unset`, not
`exclude_none`, so "remove this category" and "leave the category alone" are
different requests.

**A `PATCH` cannot null a required field.** `name`, `status`, `timing`,
`needs_double_check`, `double_checked` and `position` answer `422` when sent as
`null`; nullable fields such as `notes`, `need`, `location` and
`quantity_packed` accept it and clear.

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

A route owns options and notes, and an option owns departures. Like packing
items, a child is created under its parent and addressed on its own afterwards.

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/api/transport-routes` | none | Every route by `position`, then `id`, with its options and their departures nested, and its `note_entries`. |
| `PUT` | `/api/transport-routes/order` | none | `200` with every route, as `GET /api/transport-routes`, in the new order. Body `{"route_ids": [..]}`; see "Ordering" below. |
| `POST` | `/api/transport-routes` | none | `201`. `from_place` and `to_place` are required and non-empty; `group_name` and `notes` optional. The route joins the end of its group. |
| `GET` / `PATCH` / `DELETE` | `/api/transport-routes/{id}` | none | `404` when missing. A `PATCH` changing `group_name` moves the route to the end of its new group, unless it also sends `position`. Deleting takes the options, departures, notes and links with it. |
| `PUT` | `/api/transport-routes/{route_id}/order` | none | `200` with the route, as `GET` answers it, options in the new order. Body `{"option_ids": [..]}`; `404` for an unknown route; see "Ordering" below. |
| `PUT` | `/api/transport-routes/{route_id}/note-order` | none | `200` with the route, its `note_entries` in the new order. Body `{"note_ids": [..]}`; `404` for an unknown route; see "Ordering" below. |
| `POST` | `/api/transport-routes/{route_id}/options` | none | `201`. `mode` is required and non-empty. The option is appended after the route's last one. |
| `PATCH` / `DELETE` | `/api/transport-options/{id}` | none | Deleting takes the option's departures with it. |
| `POST` | `/api/transport-options/{option_id}/departures` | none | `201`. `day_type` is `weekday` or `holiday`; `time` is `HH:MM`. `irregular` defaults to `false`. |
| `PATCH` / `DELETE` | `/api/transport-departures/{id}` | none | |
| `POST` | `/api/transport-routes/{route_id}/notes` | none | `201` with the note. Body `{"title", "description", "links": [{"url", "title"?}, ..]}`. Appended after the route's last note. `404` for an unknown route. |
| `PATCH` / `DELETE` | `/api/transport-notes/{id}` | none | `404` when missing. `PATCH` takes the same fields, all optional; `links`, when sent, replaces the whole list. `DELETE` is `204` and takes the links with it. |

Every route carries `group_name`, a string or `null`: stripped on the way in,
and a blank one is `null`.

**Every route read carries `note_entries`** — list, get, create, patch and the
three order writes — each `{"id", "route_id", "title", "description", "links",
"position"}`, by `position`. `links` is a list of `{"url", "title"}` in order,
`title` a string or `null`. `note_entries` is not `notes`: `notes` is the route's 備註, one text value, and
stays as it was; the entries are the titled notes shown below it.

**A note needs a title or at least one link**; a description alone is not
enough. A `title`, the note's or a link's, is stripped and a blank one is
`null`. Each link's `url` is stripped, and a missing or blank one is a `422`
rather than dropped. On create the schema checks
the rule, so the `422` is FastAPI's list (`Value error, A note needs a title or
at least one link.`). A `PATCH` is checked by the router against the note as it
would be after the change, so clearing the title of a note that keeps a link is
fine, and its `422` is the plain string `A note needs a title or at least one
link.` `links: null` is a `422`; `links: []` clears them, subject to the rule.

### Ordering

`PUT /api/transport-routes/order` with `{"route_ids": [..]}` gives every route
`position` 0, 1, 2… in that order; `PUT /api/transport-routes/{route_id}/order`
with `{"option_ids": [..]}` does the same for the options of one route, and
`PUT /api/transport-routes/{route_id}/note-order` with `{"note_ids": [..]}` for
its notes. The order must name **every route (or every option, or note, of that
route) exactly once**, as the packing-list order does for items, and an empty
list on an empty set is accepted. **A route order must also keep each group
together** (`group_name`, null a group of its own). Anything else is a `422`
whose `detail` is a plain string, and nothing is changed:

| Body | `detail` |
| --- | --- |
| an id named twice | `Route 7 appears more than once in the order.` / `Option 7 …` / `Note 7 …` |
| an unknown id, or another route's option or note | `Not among the routes: routes 7.` / `Not on this route: options 7.` / `Not on this route: notes 7.` |
| one left out | `The order must name every route among the routes; missing routes 7.` / `… every option on this route; missing options 7.` / `… every note on this route; missing notes 7.` |
| routes of one group in two separate runs | `The order splits the "彰化" group: a group's routes must be adjacent.` (`the ungrouped group` for `null`) |

**A departure is unique per option, day type and time.** Creating one that
already exists, or a `PATCH` that would make one collide, is a `409` with
`That departure already exists for this option.` The same time on the other day
type is a different departure. Departures read back ordered by `day_type` (alphabetically, so `holiday` before
`weekday`), then `time`, and `time` is serialised as `HH:MM:SS`.

**A `PATCH` cannot null a required field.** `from_place`, `to_place`, `mode`,
`advance_ticket`, `day_type`, `time`, `irregular`, `position` and a note's `links` answer `422`
when sent as `null`; nullable fields such as `notes` accept it and clear.

## Trips — `/api/trips`

A trip owns legs. Like packing items, a leg is created under its trip and
addressed on its own afterwards.

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/api/trips` | none | The same four shelves as packing lists — `free`, `auto_saved`, `saved`, `templates` — plus `evict_next`, the trip the next `usage: past` would drop (or `[]`). Every trip has its legs nested. `free`, `saved` and `templates` are newest `created_at` first, then highest `id`, as for lists; `auto_saved` is newest `auto_saved_at` first. Every trip carries the fields under "A trip" below. |
| `POST` | `/api/trips` | none | `201`. `name` is required and non-empty; `kind` is `free` (the default, 未使用) or `template`, and `saved` is a `422`. Optional `copy_from_id` copies another trip of any kind (see `business-rules.md`, "Copying a trip"): `404` `Trip to copy from not found.` for an unknown one, and `422` `start_date is required to copy a trip with legs.` when it has legs and no `start_date` (a date) was sent. `start_date` is needed only when some leg of the source has a `departs_at`. Nothing is written on either refusal; a `start_date` without `copy_from_id` is ignored. The response adds `unlinked_from`, `[{from_place, to_place, packing_list_name}]`, empty unless a copied leg had a list. Never refused by 自動保存. |
| `POST` | `/api/trips/bulk-delete` | none | `204`. Body `{"ids": [..]}`. All or nothing: an id naming no trip is a `404` and nothing is deleted. Legs go with each trip; a linked packing list is kept and unlinked. |
| `GET` / `PATCH` / `DELETE` | `/api/trips/{id}` | none | `404` when missing; an `id` that is not an integer is a `422`, and that is what the retired `GET /api/trips/current` now answers. `PATCH` takes `name`, `notes`, `archive_note`, `done`, `ticket_status`, `round_trip`, `outbound_title`, `outbound_notes`, `return_title`, `return_notes`, `kind`, `usage` and `evict_confirmed`, with the same kind moves and refusals as a packing list; `usage: past` into a full 自動保存 is a `409` naming the trip that would go (`Auto-save already holds 10 trips. …`). `done: true` on a trip that is not ready, and `round_trip: false` while 回程 holds anything, are `422`s (below). Deleting takes the legs with it. |
| `POST` | `/api/trips/{trip_id}/legs` | none | `201`. `from_place` and `to_place` are required; everything else is optional. |
| `PATCH` / `DELETE` | `/api/trip-legs/{id}` | none | `404` when missing. The same for an entry and a backup. Deleting an entry takes its backups with it. |
| `POST` | `/api/trip-legs/{id}/backups` | none | `201` with the new 備案 of that entry. The same body and refusals as creating a leg, except that a `packing_list_id` is a `422` (`A backup cannot link a packing list.`), a `section` is stored as null, and a backup cannot have backups (`422`, `A backup cannot have backups of its own.`). `404` for an unknown entry. Never touches `done`. |

### A trip

| Field | Type | Meaning |
| --- | --- | --- |
| `id`, `name`, `notes`, `archive_note`, `created_at` | | As before; `notes` is the trip's overall 備註, one-way or round trip. |
| `kind`, `usage`, `auto_saved_at` | | The shelf, as for a packing list. |
| `done` | boolean | 已準備完成. |
| `ready` | boolean | Read-only: whether `done` may be set now. |
| `ticket_status` | `"not_bought"` \| `"not_needed"` \| `"bought"` | 未買票 / 無需買票 / 已買票. `not_bought` on every new trip and every copy. |
| `round_trip` | boolean | 單程 (`false`) or 來回. |
| `outbound_title`, `outbound_notes`, `return_title`, `return_notes` | string or `null` | 去程's and 回程's title and remark. |
| `legs` | array | The legs, below, by `departs_at` with untimed ones last, then `id`. Backups are not among them; each is under its entry's `backups`. |

`ticket_status` and `round_trip` refuse `null` on a `PATCH`.

### A leg

| Field | Type | Meaning |
| --- | --- | --- |
| `id`, `trip_id` | integer | |
| `from_place`, `to_place` | string | Required, non-empty. |
| `departs_at`, `arrives_at` | ISO 8601 with offset, or `null` | Both optional. |
| `transport_type` | one of `hsr`, `train`, `metro`, `bus`, `coach`, `car`, `bike`, `walk`, `flight`, `ship`, `other` | Default `other`. |
| `direction` | string or `null` | 方向. |
| `ride_type` | one of `hail`, `own_car`, `car_rental`, `own_bike`, `youbike`, `moovo`, `bike_rental`, or `null` | Only the entry's type's values are accepted when sent. |
| `section` | `"outbound"` \| `"return"` \| `null` | Stored null on a one-way trip; `outbound` on a round trip unless `return` is sent. |
| `service`, `service_number`, `seat`, `ticket_type`, `booking_code`, `notes` | string or `null` | |
| `price` | integer ≥ 0 or `null` | |
| `booked`, `paid`, `collected` | boolean | The three labels, default `false`. |
| `has_booked`, `has_paid`, `has_collected`, `has_booking_code` | boolean | Whether the entry shows each label and the code. Optional on create (the type's default when left out); always present in a response. |
| `packing_list_id` | integer or `null` | |
| `packing_list_name` | string or `null` | Read-only: the linked list's name. |
| `backup_of_id` | integer or `null` | Read-only: the entry this one is a 備案 of. |
| `backups` | array | Read-only: this entry's 備案, in the same order as `legs`. Each has the fields above but `packing_list_name` and `backups`. `POST .../backups` answers in that shape too. |

**Times carry a zone.** `departs_at` and `arrives_at` are ISO 8601 with an
offset, for example `2026-09-24T18:06:00+08:00`; a time without one is a `422`.
**When `departs_at` is set and `arrives_at` is not, `arrives_at` is stored as
`departs_at`**, on create and on the leg as a `PATCH` leaves it.

**`arrives_at` must not be before `departs_at`**, else `422`; equal is fine.
On create the schema checks it, so the `422` is FastAPI's list (its `msg` is
`Value error, arrives_at must not be before departs_at`). A `PATCH` is checked
by the router against the merged values, so moving only one of the two is
judged against the stored other, and its `422` is the plain string
`arrives_at must not be before departs_at`.

**Switches and ride types are judged against the type.** `has_x: true` for a
label the type lacks, `has_x: false` for one it fixes on, or a `ride_type`
that is not the type's, is a `422`: FastAPI's list on create, a plain string
on a `PATCH` (for example `A walk entry has no booked.`). A `PATCH` changing
`transport_type` resets every `has_*` it does not send to the new type's
default and judges the ones it sends against the new type. A `ride_type` is
judged only when sent; one kept from an earlier type stays stored. See
`business-rules.md`, "Trip entries and their types".

**Linking a list.** `packing_list_id` naming no list is a `404`. A list already
linked from another leg is a `409` with `That packing list is already linked to
another leg.`; a `PATCH` that keeps the leg's own link is not a collision.
Deleting a linked list keeps the leg and clears its link.

**A leg's `ticket_type` is remembered** as a `ticket_type` label option.

**`done` is 已準備完成**, a boolean, `false` on every new trip and on every
copy. **`done: true` on a trip that is not ready is a `422`** whose `detail`
names what is missing — `The trip is not ready: tickets not bought.`,
`The trip is not ready: 2 entries have unticked labels.`, or both joined by
`; ` — judged on the trip as the same `PATCH` leaves it. `done: false` is never
refused. **A write that leaves a done trip not ready clears `done`** in the
same transaction: a leg created or patched, or `ticket_status` set back to
`not_bought`. A backup counts for neither `ready` nor this. It is independent of `kind` and `usage`: setting it moves the
trip to no other shelf, and changing `usage` leaves it alone.

**`round_trip: false` is a `422`** while any leg is in `return` or
`return_title` or `return_notes` has text (`Cannot make the trip one-way: 1
entry is in the return. Move or delete them first.`); clearing them in the
same `PATCH` counts. Success sets every leg's `section` to `null`.
`round_trip: true` puts every leg with no section in `outbound`.

**A `PATCH` cannot null a required field.** `name`, `kind`, `usage`, `done`,
`ticket_status` and `round_trip` on a trip, and `from_place`, `to_place`,
`transport_type`, `booked`, `paid`, `collected` and the four `has_*` on a leg,
answer `422` when sent as `null`; nullable fields such as `notes`,
`archive_note`, `departs_at` and `arrives_at` accept it and clear.

## Notes — `/api/notes`

筆記. A note is `{"id", "group_name", "title", "description", "links",
"position"}`: `links` is a list of `{"url", "title"}` in order, `title` and
`group_name` strings or `null`.

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/api/notes` | none | Every note by `position`, then `id`, with its links. |
| `PUT` | `/api/notes/order` | none | `200` with every note, as `GET`, in the new order. Body `{"note_ids": [..]}`; see "Ordering" below. |
| `POST` | `/api/notes` | none | `201` with the note. Body `{"group_name"?, "title", "description"?, "links"?: [{"url", "title"?}, ..]}`. The note joins the end of its group. |
| `PATCH` | `/api/notes/{id}` | none | `200` with the note. Every field optional; `links`, when sent, replaces the list, and its order is the links' order. A changed `group_name` moves the note to the end of its new group. |
| `DELETE` | `/api/notes/{id}` | none | `204`; takes the links with it. |

**A note needs a title.** `title` is stripped, and a missing or blank one is a
`422` (FastAPI's list), on create and on a `PATCH`; `title: null` is a `422`
too. `group_name` is stripped and a blank one is `null`, which is the ungrouped
group. A link's `url` is stripped and its `title` stripped with a blank one
`null`; a missing or blank `url`, or `links: null`, is a `422`. An
unknown id is a `404` with `Note not found.`

### Ordering

`PUT /api/notes/order` gives every note `position` 0, 1, 2… in the order of
`note_ids`. It must name **every note exactly once** and keep **each group
together**; the refusals are the transport route ones with `note` for `route`
(`Not among the notes: notes 7.`, `The order splits the "住宿" group: a group's
notes must be adjacent.`, `the ungrouped group` for `null`), each a `422` that
changes nothing.

## Backup — `/api/backup`

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `POST` | `/api/backup` | none | Copies every table, and the readable tabs, to the Travel sheet. No body. `200` with `{"tabs": n, "rows": {"<table>": n, ...}, "backed_up_at": "<ISO 8601 with offset>"}`. |

| Status | When |
| --- | --- |
| `409` | Another backup holds the lock. |
| `422` | Every table is empty, so nothing was written. |
| `503` | Sheets is not configured, cannot be reached once retries are spent, or refuses the key or the sheet (403/404). |

The request returns when the backup has finished, a few seconds; it does not
stream. There is no restore endpoint: restoring is `scripts/restore_sheet.py`.
Both are described in `sheet-backup.md`.
