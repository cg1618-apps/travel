# API

Last verified: 2026-09-19

**What this is for.** Every HTTP endpoint this application serves. The
authority is FastAPI's own route table — if a row here and the dump disagree,
the dump wins and this page is wrong:

```bash
venv/Scripts/python.exe -c "from app.main import app; [print(r.methods, r.path) for r in app.routes]"
```

The rules behind these endpoints — what fills the cap, what a copy carries —
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
| Error shape | every endpoint | `{"detail": "a sentence"}`. A plain string, never a structured object — the frontend's `fetchJson` reads `detail` and shows it. Anything a caller needs to *act* on arrives as data on a normal response, not inside an error. |
| Create | every `POST` | `201` with the created object. |
| Update | every `PATCH` | `200` with the updated object. Only the fields present in the body change; omitting a field leaves it alone. |
| Delete | every `DELETE` | `204` with no body. |
| Unknown id | every `{id}` path | `404` with a generic message. |
| Unknown enum value | any field typed as one | `422` from the schema, before the database's `CHECK` constraint is reached. The constraint is the backstop, not the error message. |
| The cap | `POST /api/packing-lists`, `PATCH /api/packing-lists/{id}` | `409` when the action would destroy a list, naming it. Repeat the request with `evict_confirmed: true` to proceed. See below. |

## Table of contents

- [Health — `/api/health`](#health--apihealth)
- [Packing lists — `/api/packing-lists`](#packing-lists--apipacking-lists)

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
| `GET` | `/api/packing-lists` | none | The three shelves, plus `evict_next`. |
| `POST` | `/api/packing-lists` | none | Create a list, optionally copying another's items. `409` if it would evict. |
| `GET` | `/api/packing-lists/{id}` | none | One list with its items, in `position` order. |
| `PATCH` | `/api/packing-lists/{id}` | none | Change any of `name`, `departure_at`, `saved`, `template`, `leg`, `pair_id`. `409` if un-saving would evict. |
| `DELETE` | `/api/packing-lists/{id}` | none | `204`. Items go with it. |

### The index

`GET /api/packing-lists` returns four fields, all arrays of list summaries:

| Field | What is in it |
| --- | --- |
| `recent` | Lists that are neither `saved` nor a `template` — the ones under the cap. |
| `saved` | Lists with `saved` set. |
| `templates` | Lists with `template` set. |
| `evict_next` | The slot the next working list would destroy, or `[]` when there is room. Both halves of a round-trip pair. |

A list with both flags appears on **both** shelves. It is one row either way;
the shelves are views of the flags, not categories a list belongs to.

`evict_next` exists because the `409` below cannot carry it. The refusal's
`detail` is a plain string, so the ids a confirmation dialog needs to offer
"save it instead" arrive here instead — on a response the screen has already
loaded, costing no extra request.

### Creating, and the refusal

`POST /api/packing-lists` takes the list's own fields plus two extras:

| Field | Meaning |
| --- | --- |
| `copy_from_id` | Copy this list's items. Any list will do — recent, saved or template. Definition carries, state resets. |
| `evict_confirmed` | Acknowledge that the oldest working slot may be destroyed. |

The exchange is deliberately two steps:

```
POST /api/packing-lists {"name": "Osaka"}
  -> 409 {"detail": "You already have 3 working lists. Creating another would
                     delete \"Kyoto\", the oldest. Save it first if you want to
                     keep it, or confirm to replace it."}

POST /api/packing-lists {"name": "Osaka", "evict_confirmed": true}
  -> 201
```

**A refused create changes nothing.** `copy_from_id` is resolved *before* the
cap is enforced, so a copy from a list that does not exist returns `404`
without having destroyed anything — the other order would evict a real list and
then fail the request.

**Saved lists and templates are never refused**, because they do not occupy a
slot. `PATCH` enforces the same rule when a list stops being exempt: otherwise
save-then-unsave holds five working lists with nothing complaining.
