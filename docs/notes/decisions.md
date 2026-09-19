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

## Divergences from the media tracker

The platform makes `media` the reference implementation: its conventions are the
default, and a deliberate divergence is recorded here with its reason so a later
reader can tell a decision from an accident.

- **Test fixtures build the schema by running Alembic; media's call
  `Base.metadata.create_all`.** This is the one convention of media's that must
  not be copied. Its own baseline migration records the cost: 145 revisions on a
  chain that could not build from nothing, because the models were right, the
  migrations were wrong, and no test could tell the difference. A fixture built
  from the models tests the models against themselves. The cost here is one
  `alembic upgrade head` per session, and a migration that does not run becomes
  a suite that does not start rather than a drift nobody notices for four
  months. `tests/api/test_the_fixture_runs_migrations.py` reads
  `alembic_version` — which `create_all` never writes — so the divergence
  cannot be quietly undone.

- **Revision ids are mnemonics, not sequence numbers.** `p1acking0001`,
  following media (`c1image0001`, `s1r2rootflag`, `al1n2ilist`) and food
  (`i1ngredients_the_ingredient_library`). Only `0001_baseline` is numbered, and
  it came from the app skeleton rather than from anyone's choice — food's chain
  has the same shape for the same reason.

  Worth recording because the mistake was nearly made in both directions.
  `travel`, `food` and `art` all shipped with a numbered baseline, so three
  apps appeared to agree on sequential numbering and the first hand-named
  revision here followed that apparent convention instead of the reference.
  Media's actual directory was one `ls` away. It was renamed while it was still
  unmerged, unreleased and applied only to a local database — after a release
  that stops being a rename, because a revision id already in a version table
  is stranded by changing it, and the fix becomes a migration of its own.

- **A plain integer `id` primary key; media carries a UUID `system_id` plus a
  sequence-backed `public_id`.** That pair exists there to give Google-Sheets
  round trips a stable key and users a short one. travel syncs to nothing and
  exposes no ids to anybody, so the second key would be a column with no reader
  and the first a wider index with no benefit. If sharing ever needs an
  unguessable identifier it belongs on the share token, not on every row.

- **`status`, `timing`, `leg`, `visibility` and `kind` carry
  `CheckConstraint`s.** This follows media's *discriminator* precedent
  (`ck_movies_media_type`) rather than its open-vocabulary one, where values
  live in a constants module with no constraint because the list grows. These
  five are small closed sets the application branches over exhaustively, and a
  value outside one of them is a bug rather than a new option. They are text
  plus a constraint rather than PostgreSQL `ENUM` types: adding a member to a
  PG enum inside a reversible revision is disproportionate ceremony, and the
  constraint is generated from the `StrEnum` in `app/constants.py` so the two
  cannot drift.

- **Timestamps come from the database clock (`server_default=now()`); media
  defaults them in Python from a Taipei-now helper.** Media displays them.
  Nothing here does — `created_at` exists to order the cap's eviction — so the
  database clock is correct for a row written by a migration or by hand as well
  as by the app, and needs no helper.

- **Tailwind 4 and media's design tokens, but not media's components.** The
  platform asks the four apps to read as one product, so the token names and
  values in `frontend/src/index.css` are copied from
  `media/frontend/src/index.css` — bone paper, wisteria, flat surfaces. What is
  not copied is anything media-specific, such as its per-media-type scope hues,
  and no component is shared: the apps are separate repositories by design and
  a shared component library would be a git pointer between them.

- **TanStack Query on every screen.** Media's split is query hooks for anything
  written back from the UI and plain `fetch` for read-only pages. Every screen
  here is editable — a packing list exists to be ticked off — so there is no
  page that qualifies for the plain-fetch side of that split.

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

Module 1 is built; `data-model.md` is the description of what exists and this
sketch no longer restates it. The four below are still sketches.

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
- **A round trip is two ordinary lists that know about each other.** Pairing is
  navigational: it lets the two be viewed together and says nothing more. There
  is deliberately **no logic across the pair** — nothing infers that something
  carried out must come back, because the return genuinely differs and a system
  that assumes otherwise generates noise. Rejected: one list with two check-off
  states, which models the legs as identical when they are not.
- **Pairing is not routed through a trip**, which would make a trip mandatory
  for the one case where laziness is most likely.
- **A shared `pair_id`, not a `paired_list_id` self-pointer.** Designed as a
  self-reference and built as a shared key, for two reasons found while
  writing it: a pointer holds two copies of one fact and can desync — A points
  at B while B points at C, and nothing complains — and the cap counts a pair
  as one slot, which is a distinct-count against a shared key but an awkward
  self-join against a pointer.
- **Rules and transport notes are tagged text, not structured records.** Rules
  are experience; fields would lose the thing that makes them worth writing. If
  a shape emerges after fifty of them, structure it then.
- **A trip is the natural unit to share later** — `/s/<trip>` — which is the
  argument for trips existing at all despite being optional. A packing list
  sent to someone without dates or a destination is not much use to them.

### Naming

`name_cn`, `name_en`, `aliases[]`, with `name_cn` as the display default — the
platform-wide convention, shared with `food` and `art`.

**Packing lists and items deviate: they carry a single `name`.** The convention
exists for library entities that other people's data flows into — an
ingredient, a film, an artist. A packing item is a line typed at midnight, and
a second language field plus an aliases array on each one has no reader. If a
shared trip ever needs to be read in the other language, that is a property of
the share rather than of every row.

### Packing lists, as built

The rejected alternatives, which the shipped code cannot show on its own.

- **One list entity with two independent flags, not a separate template
  table.** `saved` exempts a list from the cap; `template` offers it as a
  starting point. A list can be both, either or neither, so promoting one is a
  flag flip rather than a duplication, and there is no copying between kinds.
  Rejected: templates as their own entity, which makes "keep this actual list
  and also start from it" two rows that drift apart.

- **There is no "always packed" marker.** It was in the original design and was
  removed before anything was built. Nothing is unconditionally packed — the
  phone is, right up until the trip is strange enough that it isn't — so the
  set of things on every list is a property of the *template chosen for this
  trip*, not of the item. Templates already do that job, and two mechanisms for
  one job is how they drift apart. It also had no answerable seed source: the
  lists whose always-items the union would be read from are the ones the cap
  deletes.

- **Status is a triple, not a boolean.** Without `no_need` a list never reads
  as finished, and the items left unticked cannot say whether they are
  forgotten or deliberately left behind — which is the distinction being
  scanned for at the door.

- **Double-check is two fields, not a fourth status value.** The state worth
  seeing is *packed and still unverified*: the passport is in the bag and
  nobody has looked at the expiry date. A single mutually-exclusive field
  cannot express it. Rejected: `not_packed / packed / needs_double_check /
  no_need`, which forces an item to be either checked off or flagged.

- **Quantity is a target and a count, which forced it to be numeric.** It was
  designed as free text — "2 pairs", "enough for 5 days" — and changed when the
  packed count was added, because "3 of 5" cannot be computed from a string.
  The number and its unit are separate columns. The cost is real: an
  unquantifiable amount is rounded or left null with the detail in `notes`. The
  benefit is that being short is visible at a glance, which is the failure a
  packing list exists to catch.

- **The count suggests the status; it never sets it.** An item may be marked
  `packed` while short, because sometimes three of five is what you are taking,
  and a derived status would force you to edit the target to say so.
  Over-packing is not an error either. Rejected: deriving status from the count
  whenever a quantity is set, which is one source of truth and no way to say
  "three is enough".

- **A pair counts as one slot against the cap.** The pair is how a trip is
  actually thought about; charging it two would punish the round trip for being
  modelled honestly.

- **Eviction refuses before it deletes, and the refusal is a plain string.**
  `detail` is a plain string on every endpoint, matching media, so the ids the
  confirmation dialog needs arrive as `evict_next` on the index instead — data
  on a normal response rather than structure smuggled into an error.

- **Options are learned, not curated.** Typing a category records it; a small
  screen renames, reorders and prunes. Rejected: a curated list seeded before
  use, which makes autocomplete useless until the seeding is done. Because an
  item holds the text rather than a reference, a rename rewrites the items, a
  name collision means merge, and a delete leaves the items alone.

- **Due-now is computed on the frontend.** The viewer's calendar day is the one
  that matters and the server's is not necessarily the same. That is what
  brought vitest into this app: it is a date boundary, wrong only on the
  evening it counts.

### Out of scope, deliberately

Itineraries and day-by-day plans. Bookings, flights and reservations. Expenses.
Anything multi-user beyond the eventual read-only share of one trip.
