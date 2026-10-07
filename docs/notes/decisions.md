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
- **Saved and template trips are kinds of `trip`**, as they are of
  `packing_list`, rather than a separate template table: a template *is* a
  trip, edited on the same page. `archive_note` (保存備註) is kept apart from
  `notes` because one is written before the trip and the other after. Saving
  and a trip's 狀態 are set by hand, are reversible and lock nothing; moving a
  trip on automatically once its last leg ended, and a read-only saved state,
  were both considered and not wanted. See "Kinds replace flags" below.
- **A copied trip moves to a start date and does not take the lists.** Its
  legs shift by whole Taipei days so clock times and gaps survive — the same
  idea as the sheet import's `--trip-start`. Copying the linked packing lists
  as well was considered and declined: lists are linked by hand, so the copy
  reports which legs had one instead (`unlinked_from`).

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
  round trips a stable key and users a short one. travel exposes no ids to
  anybody, and its sheet backup needs no stable key because a restore
  *replaces* every table with the ids it backed up rather than merging into
  existing rows (see "The sheet backup" below). So the second key would be a
  column with no reader and the first a wider index with no benefit. If sharing ever needs an
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
  Nothing here does — `created_at` only orders the packing-list index — so the
  database clock is correct for a row written by a migration or by hand as well
  as by the app, and needs no helper.

- **The list screen is a spreadsheet, with a checklist beside it.** The first
  build grouped items by a mode chosen from "When / Category / Bag" and added
  them through a box labelled "Add something". Both were rejected on sight once
  there was something to look at, and for the same reason: they put the data
  model's vocabulary on screen and asked the reader a question about it.
  Grouping is not a thing anyone wants; seeing their list is.

  The references are the two tools this list would otherwise live in. A
  **spreadsheet** for planning — every column visible, every header sorting,
  every cell editing in place, no save button — and **Google Tasks** for
  working through — a tick, a name, a quiet second line, done items folded
  away. Two views rather than one, because one screen doing both jobs is what
  produced the first attempt.

  What went with it: the grouping toggle, the modal item editor (every field it
  held is now a column), and due-now highlighting.

- **Packing timing became an ordinary column.** It was designed to drive the
  layout, with groups highlighted as they fell due. In practice the highlight
  competed with the list for attention and the grouping hid things. It is now
  the 打包時機 column, sorted in escalating rather than alphabetical order. The
  `dueTimings` function and its boundary tests were deleted; `daysUntil`
  survives, because "leaving tomorrow" is still worth saying and is still a
  date boundary worth testing.

- **The index carries `item_count` and `settled_count`.** The list of lists
  shows "2 / 6" per row. Sending every item of every list so the client could
  length them would be a page-sized payload to render one fraction, so the
  counts are computed where the rows already are.

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

## The catch-all serves real files, the way `media` does

The SPA catch-all inherited from the skeleton answered **every** non-API path
with `index.html`. That is correct for a client route and wrong for a file that
actually exists in the bundle: `/favicon.svg` came back as the SPA's HTML under
`text/html`, and the browser discarded it. Only `/assets` was mounted as
`StaticFiles`, and Vite copies `frontend/public/` to the **root** of the bundle,
not into `assets/` — so nothing served it. Nothing sits in front of this app
either; cloudflared connects straight to uvicorn, so there was no proxy to cover
the gap. The icon shipped in the repository and had never been served.

**The fix is `media`'s resolve-and-confine block, adopted rather than
redesigned**, per the platform's house-style rule that `media` is where a
convention is looked up. The handler resolves `dist / full_path`, and serves it
only when it is inside the dist directory, is not the directory itself, and is a
real file; otherwise it falls back to `index.html`.

Rejected: **special-casing the icon paths** — a list of `/favicon.svg`,
`/favicon.ico`, `/robots.txt` and whatever comes next. It is shorter today and
it is a list somebody has to remember to extend, with the same silent failure
each time a file is added to `frontend/public/`. Rejected: **mounting the whole
dist as `StaticFiles` with `html=True`**, which would serve the files but hand
the client-route fallback to Starlette, and with it the `/api` 404 guard this
app cannot give up.

**The `/api` guard stays the only prefix guard here.** This app's health path is
`/api/health`, declared so in the platform's `apps.yml`, so the `api` prefix
already covers the deploy probe. `food` carries a second `health` guard because
its health path is `/health`; copying that guard here would 404 nothing this app
serves today and would read as a rule rather than as the consequence of a
per-app path.

**The `.resolve()` + `is_relative_to()` + `is_file()` guard is load-bearing
security, not tidiness.** `full_path` is user-controlled, and without the
confinement `/..%2F.env` reads the app's own credentials from beside the bundle.
`tests/test_spa_routing.py` asserts both halves — that a real file in the bundle
is served as itself, and that a traversal attempt is not — and the `.env` file
its traversal test writes is load-bearing: `is_file()` is False for a path that
does not exist, so without a real secret to leak the test would pass against an
unguarded handler.

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

Modules 1 to 3 are built (packing lists, trips, transport); `data-model.md` is
the description of what exists and this sketch no longer restates them. The
three below are still sketches, or were superseded.

- **Trip** — built as a name, notes and legs; see "Sheet parity" below.
- **BuyingItem** — name, a `bought` flag, notes, optionally attached to a trip.
- **Rule** — text and tags.
- **TransportNote** — superseded by routes, options and departures; see "Sheet parity" below.

### The decisions behind that shape

- **A packing list does not require a trip.** The list is the thing being used
  and creating a trip first is ceremony, so a list stands on its own and
  `packing_list` has no `trip_id` at all. A list joins a trip only by a leg
  linking it — see "A leg links the list" under "Sheet parity" below, which
  superseded the nullable `trip_id` this sketch first proposed. The same
  instinct as `food`'s ingredient stubs: the app must never demand bookkeeping
  before it is useful.
- **Lists are disposable; templates and saved lists are kept.** A finished
  list marked 過去使用 is auto-saved, only the most recent five slots of those
  stay, older ones fall away, and a list worth keeping is saved or made a
  template explicitly. Without that, "copy a previous list" degrades into a
  wall of forty names and stops being used — which would take the most
  valuable feature with it.
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
  at B while B points at C, and nothing complains — and 自動保存 counts a pair
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

- **One list entity with a `kind`, not a separate template table.** A
  template is a list like any other, opened and edited on the same page.
  Rejected: templates as their own entity, which needs a second set of
  endpoints and screens for what is the same shape of data. 當作範本 does copy
  — see "Kinds replace flags" below for why that is now wanted.

- **There is no "always packed" marker.** It was in the original design and was
  removed before anything was built. Nothing is unconditionally packed — the
  phone is, right up until the trip is strange enough that it isn't — so the
  set of things on every list is a property of the *template chosen for this
  trip*, not of the item. Templates already do that job, and two mechanisms for
  one job is how they drift apart. It also had no answerable seed source: the
  lists whose always-items the union would be read from are the ones
  自動保存 drops.

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

- **A pair counts as one 自動保存 slot.** The pair is how a trip is actually
  thought about; charging it two would punish the round trip for being
  modelled honestly. Dropping the slot deletes only the auto-saved halves: a
  half still 使用中 was never in the queue.

- **Dropping a slot refuses before it deletes, and the refusal is a plain
  string.**
  `detail` is a plain string on every refusal a router raises, matching media
  (only FastAPI's own schema `422` is a list), so the ids the
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

## Sheet parity

The owner plans in a Google Sheet; the app was extended until it could hold
the four tabs in scope (`彰化回台北`, `台北去彰化`, `Transportation`,
`This time`) and then loaded them. Each decision as it ended up.

- **An item is a name plus a detail, not a parent with child items and not one
  folded name.** `鑰匙` + `家鑰匙` and `鑰匙` + `宿舍鑰匙` are two ordinary rows
  sharing a name and differing in `detail`. Rejected: parent and child items,
  which adds a tree to a list that is a flat sheet, with its own ordering,
  deletion and check-off rules; and folding the variant into the name
  (`鑰匙 家鑰匙`), which cannot be grouped, cannot be shown the way the sheet
  shows it, and cannot be suggested. The sheet UI groups by equal runs of
  category and name only under position order; any other sort shows full names,
  because a blank cell under a foreign order is ambiguous. `+ 變化` inserts a
  row directly below with `after_id`, shifting later positions in one
  transaction.

- **`need` is closed, `location` is open.** `need` (`need`, `bring`, `buy`) is a
  small set the application branches over and is a `CheckConstraint` with an
  explicit null arm; `location` is where something is got and grows with use, so
  it is free text suggested by `label_option` (kind `location`), like `category`.

- **Departures are rows, not four text columns per day type.** The sheet's
  早 / 中 / 下午 / 晚 columns are a display of clock times, so each time is a
  `transport_departure` row with a day type and an `irregular` flag, unique per
  option, day type and time, and the screen buckets by the clock (12:00, 14:00,
  18:00). Rejected: storing the four cells as text, which cannot be asked for
  the next departure and lets a time sit in the wrong column unnoticed. The
  importer checks each time against the column it came from and reports
  mismatches.

- **A leg links the list; a trip does not own the pair, and `packing_list` has
  no `trip_id`.** `trip_leg.packing_list_id` is a nullable, unique foreign key,
  `ON DELETE SET NULL`, so deleting a list keeps the leg. A linked list takes its
  date from the leg (the Taipei calendar day). Rejected: a trip owning the
  outbound and return pair, which fixes every trip to two legs and two lists;
  and `packing_list.trip_id`, which the first packing revision's docstring
  intended. That intention is superseded: a trip with several legs needs to say
  *which journey* a list is for, and only the leg knows.

- **There is no current trip any more.** It began as the trip with the soonest
  leg still ahead, else the one whose legs ended most recently — which switched
  trips mid-journey (while one trip's leg was under way, a trip with a later
  leg was already current), never chose a trip with no legs, and kept showing a
  finished trip until something newer had a leg. `k1ind0000001` made it follow
  狀態 instead: the 使用中 trip, else the 未來使用 one, legs only ordering trips
  within a group. That rule was then retired along with the `/trip` page that
  showed it; see "An index with tabs replaces the current trip".

- **Status is stored as three values and tapped as two.** `no_need` stays in
  the data because a decision not to pack is not the same as forgetting, and
  folding it into `not_packed` would erase that. One tap toggles not packed and
  packed; `no_need` is a long-press or the row menu, and one tap returns it to
  not packed. Double Check lives on the same menu so the tick only means packed.

- **A reset leaves `no_need` alone.** 重設狀態 sets packed items back to not
  packed, clears the packed count and Double Check confirmation, and skips
  `no_need`, because that is a choice about the list rather than progress
  through it. It is the copy rule's reset half minus `no_need`.

- **The UI speaks the sheet's own words; stored values are English.** Headers
  and values such as 未打包 and 出發前晚 are the sheet's, so the owner reads the
  same vocabulary in both places. Only `Double Check` stays English. The
  `Transportation` and `This time` tabs started out under their sheet names and
  are now 交通 and 行程, at the owner's request: a nav bar mixing two
  languages read worse than a screen not matching its tab's spelling. Every display string lives in
  `frontend/src/lib/labels.js` and a test asserts each stored value has one.

- **A required field cannot be nulled through `PATCH`; an explicit null is a
  422.** The update schemas type every field `X | None = None` so omitted means
  leave alone, which also let a caller send null for a NOT NULL column and reach
  the database as a 500 (or a misleading departure collision).
  `NonNullableUpdate` in `app/schemas/base.py` names the required fields and
  refuses them. Nullable fields still accept null to clear them.

- **The importer defaults blank status cells and says so.** A blank 打包狀態,
  Double Check or 打包時機 becomes 未打包, 不需確認 or 隨時, and the row is
  reported naming which columns were blank. Rejected: refusing the import,
  which blocks on a cell the owner does not think of as missing; and defaulting
  silently. An unknown word, by contrast, is refused.

- **The importer ships in the runtime image.** `scripts/import_sheet.py` and
  `openpyxl` are in the production container, so the box is loaded from inside
  it by the manager session rather than from a developer machine that cannot
  reach it. It refuses, writing nothing, when any list, route or trip it would
  create already exists, and it runs once per database rather than as a sync.

- **`bag` is kept and not shown.** The sheet has no bag column, so the sheet UI
  does not render one, but the column, its option kind and the copy rule stay.
  Removing it would be a destructive migration for a field the owner may want
  back, and leaving it costs nothing.

- **A trip carries `visibility`, added by its own revision.** A single trip's
  information is the thing expected to be shared, so `trip` carries `private` /
  `unlisted` / `public` like `packing_list`, everything `private`, and nothing
  reads it yet. `t1rip0000001` shipped without it; the column arrived as
  `t2rip0000002` rather than as an edit to `t1rip0000001`, because that
  revision had already been applied to a development database holding the
  imported sheet, and an edited revision leaves such a database stamped with an
  id whose contents it never ran. The revision writes the three values out
  rather than building them from `Visibility`, so it keeps describing what the
  schema was if the enum later changes.

- **`tzdata` is a runtime dependency.** Every leg time and every derived date
  is Asia/Taipei through `zoneinfo`, which reads the operating system's zone
  database — and Windows has none, so without `tzdata` the development machines
  cannot name the zone at all.

## Kinds replace flags; 自動保存 is free + past

Lists and trips used to carry independent booleans — `saved` and `template`
on a list, `archived` and `template` on a trip — with a three-slot cap on
"working" lists and a date rule for the current trip. `k1ind0000001` replaced
all of it with one model shared by both tables: a `kind` (`template`, `saved`,
`free`), a `usage` that only a `free` row has, and `auto_saved_at`. The rules
are in `business-rules.md`; this is why.

- **Impossible combinations are unstorable.** Two independent flags allowed a
  saved template, an archived template and states the screens had to reconcile
  (an archived template was listed as archived *and* offered by 從範本). One
  `kind` column puts every row on exactly one shelf, and four check
  constraints keep `usage` and `auto_saved_at` consistent with it.
- **自動保存 is `kind = free AND usage = past`, not a fourth kind.** "A 一般 row
  marked 過去使用 is auto-saved" is then true by construction rather than kept
  in step by code, and leaving 過去使用 returns the row to 一般 with nothing
  else to undo.
- **One queue rule for two tables.** Lists and trips fill 自動保存 the same way
  (`app/services/domain/auto_save.py`), differing only in the limit — five list
  slots, ten trips — and in a pair of lists sharing a slot.
- **封存 and 保存 were one idea under two words.** A trip was 封存 and a list
  保存; both meant "keep this, it is done". Both are 保存 now, and the remark
  written afterwards is 保存備註 on both.
- **Templates are made by copying.** 當作範本 creates a new template from any
  list or trip rather than flipping the original, so a template's kind never
  changes and nothing becomes or stops being one by `PATCH`. On a trip it keeps the legs on their own dates.
- **The current trip followed usage rather than dates**, until it was retired
  — see "An index with tabs replaces the current trip".

Rejected:

- **Keep the booleans and add a status.** Every impossible combination
  survives, and a third column has to be kept consistent with two others.
- **A table per kind.** Moving a list to 保存 would be a copy between tables,
  its items and a leg's link with it, for what is a change of shelf.

Two choices made in the migration and the importer:

- **A row that was both saved (or archived) and a template becomes a template
  only**, not a template plus a saved copy. Templates are never dropped, so
  nothing is lost; a copy would mean duplicating items inside a migration for a
  set that was probably empty. The downgrade cannot tell such a row apart, so
  it comes back a template only.
- **The sheet importer creates `free` rows, 未使用**, not saved ones. Under the
  cap, saving was what kept the import from being evicted. Nothing is dropped
  from 一般 any more — only from 自動保存, and only once a row is set to
  過去使用 by hand — so there is nothing to protect them from, and an imported
  list saved by default would have to be un-saved before it could be used.

## An index with tabs replaces the current trip

`/trip` showed one trip — the usage-based current trip — with every other trip
in stacked 一般 / 保存 / 範本 sections below it and 自動保存 on a page of its
own; `/lists` stacked its four shelves the same way. Both are now indexes with
browser-style tabs, and 行程 opens `/trips` like 打包清單 opens `/lists`.

- **The usage-based current trip was retired, not refined.** The page left the
  trip on screen out of every section below it, so a lone 一般 trip sat in no
  section at all: reachable only as "the current one", on a page that listed
  everything else. Keeping a page that shows one trip meant keeping a
  second place every trip could be, and code to move the page when a 狀態
  change took the trip out of being current (使用中 → 未來使用 included, since
  another 使用中 trip would then take `/trip` over). What the current trip was
  for — "what am I using now" — is the dashboard's job, and it already picks by
  `usage`: every 使用中 and 未來使用 trip, 使用中 first. `GET /api/trips/current`
  went with the page; it now falls to `/api/trips/{trip_id}` and is a `422`.
- **Tabs, not sections.** Every row is on exactly one tab, the counts say where
  without scrolling, and the four tabs are the API's four arrays shown as they
  come, so the screen cannot drop a row the API returned. The tab is in
  `?tab=`, so Back and a reload return to it.
- **Shelves are newest `created_at` first, for trips as for lists.** Trips were
  ordered by their latest departure with legless trips last, which put a trip
  just created without legs at the bottom of the tab it was created into, and
  reordered the tab whenever a leg's time was edited. `created_at` is stable,
  and it is what lists already used. The leg picker orders by it too, and shows
  the created date, because two lists with the same name are told apart by when
  they were made.
- **Old addresses redirect.** `/trip` goes to `/trips`, and `/trips/auto-saved`
  — a page that shipped — to `/trips?tab=auto_saved`, rather than falling to
  `/trips/:tripId` and an error.

Rejected:

- **Keep a current trip, pinned above the tabs.** It is the same trip in two
  places again, and the dashboard already answers the question.
- **Keep the departure order for trips.** It is the order of the legs, not of
  the trips, and a trip with no legs has none.

## 交通 is an index of routes, the way 行程 is

`/transport` used to be every route with every option and every departure on
one long page. It is now one card per route, linking to `/transport/:routeId`,
because that is the shape `/lists` and `/trips` already have and the owner
asked for the same treatment. **The entry is the route, not the option**: a
route is what you look up ("how do I get from 彰化火車站 to 宿舍"), and the
options under it only make sense compared side by side, so they stay together
on the route's page. No endpoint changed — `GET /api/transport-routes/{id}`
already existed.

The index has no tabs: routes have no kinds and no 狀態, so a tab strip would
have one tab.

## Dark mode gets a toggle, copied from media

The dark palette was always there and followed the OS; what was missing was a
way to choose. The toggle copies the media tracker's rule and storage key
(`cg1618:theme`, stored choice beats the OS, nothing stored follows it) and its
pre-paint script in `index.html`. It is a hook rather than media's context
provider, because only the nav bar reads it — the colours themselves come from
the attribute through the CSS tokens, not from React.

## The sheet backup

The owner asked for one Google Sheet, **Travel**, doing two jobs: restoring
the database, and being readable when the app is down. They asked for those
jobs in tiers: what the dashboard shows first, then all lists and trips, then
everything. The tiers collapsed. Eight tables copied whole cost less code than
copying the dashboard's subset correctly, which would have to follow
leg → list links to stay consistent. And a partial copy cannot be restored.
So everything is backed up, and the dashboard's subset became the *readable*
tabs instead. How it works is in `sheet-backup.md`.

- **Its own Google Cloud project and service account.** `cg1618` is meant for
  all of the platform's apps, with one service account per app, and travel's
  is the first. The project that holds media's key was made for the legacy
  anime site, and the owner chose not to grow it. One key per app also means a
  leaked or revoked key reaches one sheet.
- **Readable tabs are output only.** Restore reads only the per-table tabs.
  The readable layout can then change freely, and it never has to be
  parsed back.
- **The readable set adds legs' lists to the dashboard's rule.** A trip in use
  whose return list is still 未使用 is the case where the app dying hurts.
  `交通` is readable too, though the owner asked for lists and trips, because
  transport is what is needed mid-trip.
- **`RAW`, not media's `USER_ENTERED`.** With `USER_ENTERED`, Sheets reparses
  every value. Media escapes its date columns with `'` to stop that. In
  travel, `booking_code` `0123` would lose its zero and text such as `TRUE`
  would turn into a boolean. With `RAW` there is nothing to escape. The
  `總覽` links are the one `USER_ENTERED` write, because they are formulas.
- **One request, not media's SSE.** Media streams because a full backup of
  its 52 tabs outlasts the tunnel's ~100-second idle limit. travel writes all
  its tabs in one batched call and one clear, which also keeps it far below
  Sheets' per-minute write quota. It finishes in seconds.
- **Refuse an empty database, not an emptied tab.** Media refuses a
  header-only write over any tab that holds data. In travel that would turn
  one legitimately empty table (the last route deleted) into a backup that
  refuses every night until someone clears the tab by hand. What media's guard
  was really about is a whole empty database, such as a fresh worktree's,
  which wiped its sheet on 2026-09-12. travel refuses exactly that, before
  calling Google at all.
- **Restore replaces; media's Pull upserts.** An upsert cannot remove a row
  deleted since the backup, so media needs a separate Clean step. For one
  person's data, the backup is the whole truth. The replace runs in one
  transaction and is checked fully before the first delete. It refuses a
  revision mismatch, a non-empty database without `--replace`, and a tab whose
  row count disagrees with `Backup Info`, which is how a half-written backup
  shows itself.
- **Sequences move with `ALTER SEQUENCE ... RESTART`, not `setval`.**
  `setval` is not transactional, so a dry run or a failed restore would roll
  the rows back and leave the sequences moved.
- **Restore is a command, not a button.** This was the owner's choice. When
  the app is dead, a button cannot be pressed. And the one operation that
  deletes everything should take a deliberate command. A development-only
  button was offered and declined.
- **The nightly job resolves its checkout from its own path.** Media's
  `lib.sh` assumes `~/media`, which is the hazard recorded under "Renaming
  media's checkout" in the platform's decisions.
