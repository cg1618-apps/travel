# Decisions

Why travel is the way it is. Unlike the rest of `docs/`, this page is allowed to
talk about the past: it records what was chosen, what was rejected, and the
reasoning that is still load-bearing.

## Platform decisions this app inherits

Recorded in `cg1618-apps/platform` rather than here, and summarised only so far
as they bind this app:

- **It is its own repository**, sharing no code with the other applications. The
  platform connects them by configuration, not by git pointers.
- **It shares one PostgreSQL**, with its own database and its own role.
- **It is `public`**, because repository rulesets and environments with required
  reviewers are free only for public repositories, and both gates depend on it.
- **No `pull_request`-triggered job may run on the self-hosted runner.**

## Decisions for this application

- **FastAPI, PostgreSQL, React + Vite, Alembic** — the media tracker's stack.
  Rejected: Django and a server-rendered frontend, for the same reasons
  recorded across the other apps; the deciding factor was consistency with an
  app that already works.
- **Cloudflare Access over the whole hostname, and no auth code in the app.**
  One user, no accounts. Rejected: an app-level single-user password with a JWT
  cookie, copying the media tracker — roughly 150 lines of security-sensitive
  code, written to duplicate a gate that already exists. Its one real advantage
  is failing closed: Access failing open, if a policy is deleted, exposes
  everything. That risk is accepted for now and is the reason the flip to
  `public` is treated as a deliberate, tested event rather than a config edit.
- **Sharing is anticipated, not built.** `/s/...` as the prefix for anything
  shareable, a `visibility` field from the first migration, and share tokens
  rather than accounts. All three are nearly free now and expensive to
  retrofit; none of them is implemented until sharing is actually wanted.

## The skeleton

- **The SPA catch-all refuses the `/api` prefix explicitly, rather than
  relying on route registration order.** Registering the API router first is
  necessary but not sufficient: FastAPI's `path` converter matches any string
  whenever it is reached, so ordering protects only routes that actually
  exist. Without the prefix check a mistyped endpoint returns 200 with the
  bundle's HTML, and a broken frontend call reads as a rendering bug instead
  of a missing route.
- **`create_app(dist)` is a factory so the catch-all can be mounted against a
  directory a test controls.** Nothing builds the frontend before the suite
  runs — CI builds it in a later step — so `frontend_dist/` need not exist,
  the module-level `app` then mounts no catch-all at all, and a test written
  against it passes by finding nothing to test.
- **`deploy/migrations` clears `COMPOSE_PROJECT_NAME` for `current` and
  deliberately not for `downgrade`.** `current` reaches the shared PostgreSQL,
  which lives in the platform's compose project; `downgrade` runs this app's
  own image in this app's project, where the exported name is the right one.
  The two arms differ because the containers they talk to belong to different
  projects, not by oversight.
- **Migrations run in `entrypoint.sh` on every start, and a rollback reverses
  them from the new image.** The previous image has never heard of the
  revisions being reversed, so it cannot undo them — which is why
  `deploy/migrations downgrade` runs `--entrypoint alembic` against the image
  that just failed rather than the one being rolled back to.

## Structure

Five modules, built in this order. Each gets its own design pass immediately
before it is built, not now.

| | Module | Owns | Depends on |
| --- | --- | --- | --- |
| 1 | Packing lists | lists, items, check-off, templates, pairing | — |
| 2 | Trips | an optional container: dates, destination, notes | — |
| 3 | Transport | general knowledge, and the current trip's specifics | 2 (optional) |
| 4 | Buying list | what to buy before going | 2 (optional) |
| 5 | Rules | the things learned the hard way | — |

**Packing is the important one.** The others are useful; this is the one the app
is opened for, and it is built first for that reason rather than because it is
easiest.

### Entities

- **PackingList** — a nullable `trip_id`, a nullable `paired_list_id`, a
  `template` flag, and a `leg` label (outbound, return, neither).
- **PackingItem** — name, category, a `packed` flag, notes, and an `always`
  marker for the things that are on every list.
- **Trip** — names, dates, destination, notes.
- **BuyingItem** — name, a `bought` flag, notes, optionally attached to a trip.
- **Rule** — text and tags.
- **TransportNote** — text and tags, general or attached to a trip.

### The decisions behind that shape

- **A packing list does not require a trip.** `trip_id` is nullable because the
  list is the thing being used and creating a trip first is ceremony. Attaching
  one later is a single edit. The same instinct as `food`'s ingredient stubs:
  the app must never demand bookkeeping before it is useful.
- **Lists are disposable; templates are kept.** The three most recent lists
  stay available to copy from, older ones fall away, and a list worth keeping
  is promoted to a template explicitly. Without that, "copy a previous list"
  degrades into a wall of forty names and stops being used — which would take
  the most valuable feature with it.
- **A round trip is two ordinary lists that know about each other.**
  `paired_list_id` is navigational: it lets the two be viewed together and says
  nothing more. There is deliberately **no logic across the pair** — nothing
  infers that something carried out must come back, because the return genuinely
  differs and a system that assumes otherwise generates noise. Rejected: one
  list with two check-off states, which models the legs as identical when they
  are not.
- **Pairing is a self-reference rather than a trip.** Routing it through trips
  would make a trip mandatory for the one case where laziness is most likely.
- **Rules and transport notes are tagged text, not structured records.** Rules
  are experience; fields would lose the thing that makes them worth writing. If
  a shape emerges after fifty of them, structure it then.
- **A trip is the natural unit to share later** — `/s/<trip>` — which is the
  argument for trips existing at all despite being optional. A packing list
  sent to someone without dates or a destination is not much use to them.

### Naming

`name_cn`, `name_en`, `aliases[]`, with `name_cn` as the display default — the
platform-wide convention, shared with `food` and `art`.

### Out of scope, deliberately

Itineraries and day-by-day plans. Bookings, flights and reservations. Expenses.
Anything multi-user beyond the eventual read-only share of one trip.
