# Packing lists — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The first feature in this application — a packing list you can create
from a template, fill in, and work through by when each thing is due, with the
three-list cap enforced and nothing deleted silently.

**Architecture:** Three tables behind a FastAPI router set, and a React screen
whose default grouping is packing timing rather than category. No trips: a list
carries its own nullable departure date, and module 2 adds `trip_id` later.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, Alembic, pytest, React 19
+ Vite, vitest, TanStack Query.

**Spec:** `docs/superpowers/specs/2026-09-19-packing-lists.md`. Read it before
Task 2 — every column and every enumerated value is settled there, with the
reasoning. This plan does not restate the "why".

## Conventions this module follows

The platform `CLAUDE.md` section "House style, and `media` as the reference"
makes `media`'s conventions the default and requires a deliberate divergence to
be recorded in `docs/notes/decisions.md` with its reason. These were read out of
`media` rather than recalled; the paths are given so the next reader can check
rather than trust.

| Thing | media's convention | Where |
| --- | --- | --- |
| Backend layout | packages by layer, one file per entity | `app/models/movie.py`, `app/schemas/movie.py`, `app/routers/character.py` |
| Router shape | hand-written per entity | `app/routers/character.py` — **not** the nine-media-type factory, which is specific to that family |
| Business logic | out of the router, in a domain module | `app/services/domain/*.py` |
| Schema classes | `FooBase` → `FooCreate` / `FooUpdate` / `FooResponse` | `app/schemas/movie.py` |
| Error shape | `HTTPException(detail="a plain string")`, no shared helper | `app/routers/character.py` |
| Constraint names | `ck_<table>_<what>`, `fk_<table>_<target>` | `ck_movies_media_type` |
| Tests | `tests/api/` and `tests/unit/`, `test_<subject>.py` | `tests/api/test_character_router.py` |
| Fixtures | `db_session`, `client` | `tests/api/conftest.py` |
| Test names | long sentences, not `test_it_does_x` | `test_a_nameless_character_is_a_422_not_a_500` |
| Frontend | `pages/`, `components/`, `lib/`, `api/client.js` + `api/endpoints.js` | `frontend/src/` |
| Components | PascalCase file, `export default function Name()` | `CharacterLibrary.jsx` |
| Data fetching | TanStack via `useApiQuery` for editable pages; plain fetch for read-only | `hooks/useApiQuery.js` vs `pages/detail/Character.jsx` |
| JS tests | vitest, co-located, `<module>.test.js` | `lib/autofill.test.js` |
| Doc header | `# Title`, `Last verified: <date>`, `**What this is for.**` | every file in `media/docs/` |

**Three deliberate divergences.** Each gets an entry in
`docs/notes/decisions.md`, in the commit that introduces it.

1. **Test fixtures run Alembic; media's run `Base.metadata.create_all`.** This
   is the one convention of media's that must *not* be copied — its own
   baseline migration docstring records `create_all` as the reason a 145-revision
   chain drifted from what the tests exercised, unnoticed. Divergence recorded
   in Task 1.
2. **Plain integer `id` primary key; media uses a UUID `system_id` plus a
   sequence-backed `public_id`.** That pair exists to give Google-Sheets round
   trips a stable key and users a short one. travel syncs to nothing and shares
   nothing yet. Divergence recorded in Task 2.
3. **`status`, `timing`, `leg`, `visibility` and `kind` carry
   `CheckConstraint`s.** This follows media's *discriminator* precedent
   (`ck_movies_media_type`) rather than its open-vocabulary one, where values
   live in `app/utils/constants.py` with no constraint. These five are closed
   sets the app's logic is exhaustive over, not vocabulary that grows. Recorded
   in Task 2.

## Global Constraints

- **Ports:** uvicorn 8002, Vite 5175. Unchanged by this plan.
- **One pytest at a time, machine-wide.** Take the lock before any full run:

  ```bash
  LOCK=/c/Users/cgent/AppData/Local/Temp/anime_site_pytest.lock
  until mkdir "$LOCK" 2>/dev/null; do sleep 10; done
  venv/Scripts/python.exe -m pytest -q; rc=$?
  rmdir "$LOCK"; exit $rc
  ```

  Older than 25 minutes is stale: `rmdir` it and tell the manager.
- **Every task's doc change lands in the same commit as its behaviour change.**
  A behaviour change with no doc change is an unfinished one. Task 9 is not
  where the documentation happens; it is where the scaffolding is removed.
- **Say which migration claim you are making.** `alembic upgrade head` against a
  database that already holds the earlier revisions proves the last step, not
  the chain. The from-zero proof is the real command against a scratch database.
  If only the incremental one was run, say that — the weaker claim stated
  honestly is worth more than the stronger one rounded up.
- **Re-check the revision parent at the moment you execute it**, not as this
  plan wrote it. `alembic heads` cannot see a stale parent written in prose.
- **No trips, no `/s/...` routes, no share tokens.** `visibility` ships as a
  column and nothing reads it.
- **Nothing in git mentions AI**, in any commit message or pull request body.
- **If a task is wrong once you are inside it, change the approach and say so in
  the commit message.** You are closer to the code than this plan is.

---

### Task 1: A test database that is built by migrations

Nothing in this suite has ever needed a real schema — the existing tests are
unit tests plus one subprocess run against a scratch database. Every task below
needs a session and a client, so the fixture comes first.

**It runs `alembic upgrade head`, not `Base.metadata.create_all`** — divergence
1 above. media built its fixtures with `create_all` and so ran 145 revisions on
a chain that could not build from nothing: the models were right, the migrations
were wrong, and no test could tell the difference because no test ever ran one.
A fixture is the only place that mistake is invisible.

**Files:**
- Create: `tests/api/__init__.py`, `tests/api/conftest.py`
- Create: `tests/api/test_the_fixture_runs_migrations.py`
- Create: `docs/testing.md`
- Modify: `docs/notes/decisions.md`, `docs/README.md`

**Interfaces:**
- Produces: `migrated_database` (session-scoped) — creates `travel_test`, runs
  `alembic upgrade head` against it, yields the URL, drops it `WITH (FORCE)`.
- Produces: `db_session` (function-scoped) — a `Session` on a connection inside
  a transaction that is rolled back on teardown.
- Produces: `client` (function-scoped) — a `TestClient` with `get_db` overridden
  to that session.

- [ ] **Step 1: Write the failing test**

```python
"""The fixture's own discipline, asserted rather than assumed.

A fixture that builds its schema with create_all tests the models against
themselves and says nothing about the migrations - which is how the media
tracker shipped 145 revisions on a chain that could not build from zero.
"""

from sqlalchemy import text


def test_the_test_database_is_stamped_at_head(db_session):
    # create_all leaves no alembic_version row. This assertion is the whole
    # difference between the two ways of building the fixture.
    stamped = db_session.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar()
    assert stamped is not None


def test_one_test_cannot_see_another_test_s_rows(db_session):
    # Paired with its twin below: whichever runs first writes, the other must
    # not find it. Asserts the rollback, which is silent when it fails.
    ...
```

- [ ] **Step 2: Implement**
  - Move `_admin_url` out of `tests/test_migrations_build_the_schema.py` into a
    shared place and import it in both, rather than copying it. Two copies of
    "derive the admin URL from the app's own settings" is two places to get it
    wrong.
  - Database name `travel_test`, distinct from that test's
    `travel_migration_test` — the from-zero test drops and recreates its own
    mid-session.
  - `db_session` binds to an explicit connection with an open transaction and
    rolls back; it does not `DELETE FROM` between tests.
- [ ] **Step 3: Document, in this commit**
  - `docs/testing.md`, on media's header pattern: where tests live, the fixture
    names and what each is for, how to run under the lock, and **what a negative
    test has to set up to bite**.
  - `docs/notes/decisions.md`: divergence 1, with media's own baseline docstring
    as the evidence.
  - `docs/README.md`: add `testing.md` to the table.
- [ ] **Step 4: Verify** — full suite under the lock. The existing tests must
  pass unchanged.
- [ ] **Step 5: Commit** — `test: a database fixture built by the migrations`

---

### Task 2: The three tables and the migration

**Files:**
- Create: `app/models/__init__.py`, `app/models/packing_list.py`,
  `app/models/packing_item.py`, `app/models/label_option.py`
- Create: `alembic/versions/0002_packing.py`
- Create: `tests/api/test_packing_models.py`
- Create: `docs/data-model.md`
- Modify: `docs/notes/decisions.md`, `docs/README.md`

- [ ] **Step 1: Write the failing test**

```python
"""What the schema itself refuses, and what it cleans up.

Database-level guarantees, asserted at the database level: a CheckConstraint
that exists only in the model is a constraint the migration forgot, and every
read path would still look correct.
"""


def test_an_unknown_status_is_refused_by_the_database(db_session):
    ...


def test_deleting_a_list_takes_its_items_with_it(db_session):
    # ON DELETE CASCADE at the database level, not just cascade= in the
    # relationship: eviction deletes through the ORM, but a manual DELETE
    # from psql must not leave orphans either.
    ...


def test_quantity_packed_defaults_to_zero_and_quantity_may_be_null(db_session):
    ...
```

- [ ] **Step 2: Implement the models**
  - One file per entity, per media. `app/models/__init__.py` re-exports.
  - Columns exactly as the spec's tables give them. Plain integer `id`
    (divergence 2). `packing_item.list_id` is
    `ForeignKey("packing_list.id", ondelete="CASCADE")`, mirrored on the ORM
    side with `cascade="all, delete-orphan", passive_deletes=True` as media
    does.
  - `__table_args__` carries the named `CheckConstraint`s (divergence 3) —
    `ck_packing_item_status`, `ck_packing_item_timing`, `ck_packing_list_leg`,
    `ck_packing_list_visibility`, `ck_label_option_kind` — plus
    `UniqueConstraint("kind", "value", name="uq_label_option_kind_value")`.
    **Name every constraint.** An unnamed one gets a generated name Alembic
    cannot drop in a `downgrade`, which turns the rollback hook into a lie.
  - Narrate the non-obvious ones in comments, as media's model files do.
- [ ] **Step 3: Generate, then read the migration**
  - `alembic revision --autogenerate -m "packing lists"`, then **open the file
    and check it against the models by hand.** Autogenerate does not reliably
    emit `CheckConstraint`s or `ondelete`, and both are load-bearing.
  - `revision = "0002_packing"`, `down_revision = "0001_baseline"` — **verify
    that parent against `alembic heads` now**, not against this sentence.
    travel's numbered-slug ids are its own established convention and stay.
  - A prose docstring explaining why, as media's revisions carry.
  - A real `downgrade()` dropping all three tables.
- [ ] **Step 4: Document, in this commit** — `docs/data-model.md` on media's
  header pattern and table format; `docs/notes/decisions.md` for divergences 2
  and 3; `docs/README.md`.
- [ ] **Step 5: Verify**
  - `alembic heads` — **exactly one line.** Two migrations that never touch the
    same file still collide by naming the same parent; git merges them clean and
    nothing warns you. If there are two, **reparent** — never renumber, because
    a revision id may already be applied to a database and changing it strands
    that row in the version table.
  - Full suite under the lock. `test_upgrade_head_runs_against_an_empty_database`
    now has three tables to check and stops being vacuous — that assertion was
    written for this moment. **This is the from-zero proof**; say so in those
    words, and if only an incremental upgrade was run, say that instead.
- [ ] **Step 6: Commit** — `feat: the packing list schema`

---

### Task 3: Slots, and eviction that refuses before it deletes

**Files:**
- Create: `app/services/__init__.py`, `app/services/domain/__init__.py`,
  `app/services/domain/packing.py`
- Create: `tests/api/test_slots.py`
- Create: `docs/business-rules.md`
- Modify: `docs/README.md`

**Interfaces:**
- `SLOT_CAP = 3`
- `count_slots(db) -> int` — distinct `COALESCE(pair_id, id::text)` over lists
  where `saved` is false **and** `template` is false.
- `oldest_slot(db) -> list[PackingList]` — every list in the slot with the
  earliest `created_at`, so a pair comes back as two rows.
- `evict(db, slot) -> None`
- `copy_items(db, source, target) -> None` — the spec's carry/reset table, in
  one place.

- [ ] **Step 1: Write the failing test**

```python
"""The cap, and the fixture that makes it possible to break.

A cap asserted against an empty database passes because there was nothing to
evict: green on day one, green through the change that breaks it, green
forever. `three_working_lists` is not scene-setting - it is the only reason
the refusal can fail, and the mirror case uses the same fixture so a green
proves the cap did the refusing and not an empty table.
"""


@pytest.fixture
def three_working_lists(db_session):
    """Three lists, neither saved nor templates, oldest first. Load-bearing."""
    ...


def test_three_working_lists_fill_the_cap(three_working_lists, db_session):
    ...


def test_two_working_lists_do_not_fill_the_cap(three_working_lists, db_session):
    # The mirror. Same fixture, one list removed: the count must actually move.
    ...


def test_a_round_trip_pair_counts_as_one_slot(db_session):
    ...


def test_saved_and_template_lists_do_not_count(three_working_lists, db_session):
    ...


def test_evicting_a_pair_deletes_both_lists_and_their_items(db_session):
    ...
```

- [ ] **Step 2: Implement.** Business rules live here and not in the router, per
  media's split. `count_slots` is one `SELECT COUNT(DISTINCT ...)`; the same
  expression is reused by `oldest_slot`.
- [ ] **Step 3: Document, in this commit** — `docs/business-rules.md`: the cap,
  what counts as a slot, what eviction destroys, and the copy carry/reset table.
- [ ] **Step 4: Verify** — full suite under the lock.
- [ ] **Step 5: Commit** — `feat: slot counting and eviction for the list cap`

---

### Task 4: The lists API

**Files:**
- Create: `app/schemas/__init__.py`, `app/schemas/packing_list.py`
- Create: `app/routers/packing_list.py`
- Modify: `app/main.py`, `docs/business-rules.md`, `docs/README.md`
- Create: `docs/api.md`
- Create: `tests/api/test_packing_list_router.py`

**Interfaces:**

```
GET    /api/packing-lists            -> {recent, saved, templates, evict_next}
POST   /api/packing-lists            -> 201 | 409
GET    /api/packing-lists/{id}       -> the list with its items
PATCH  /api/packing-lists/{id}       -> name, departure_at, saved, template, leg, pair_id
DELETE /api/packing-lists/{id}       -> 204
```

**The `409` detail is a plain string**, per media — `detail` is a string in
every router there, and `frontend/src/api/client.js` reads
`data?.detail` as one end to end. The dialog still needs to know *which* list
would be destroyed in order to offer "save it instead", so that comes from
`evict_next` on the **index** response, which is data rather than an error
shape. The client already has the index loaded on the screen where a list is
created, so nothing extra is fetched.

- [ ] **Step 1: Write the failing test**

```python
def test_creating_a_fourth_list_refuses_and_names_what_would_be_destroyed(
    three_working_lists, client
):
    response = client.post("/api/packing-lists", json={"name": "Osaka"})
    assert response.status_code == 409
    # Naming it is the point: a 409 saying only "cap reached" makes the client
    # guess, and the client would guess the wrong list.
    assert "Kyoto" in response.json()["detail"]


def test_nothing_is_deleted_by_a_refused_create(three_working_lists, client, db_session):
    ...


def test_confirming_creates_the_list_and_deletes_the_oldest(
    three_working_lists, client, db_session
):
    ...


def test_a_third_list_needs_no_confirmation(three_working_lists, client, db_session):
    # The mirror: delete one of the three first, then a create must be 201
    # with no confirmation and nothing evicted.
    ...


def test_a_copy_carries_the_definition_and_resets_the_state(client, db_session):
    # status -> not_packed, quantity_packed -> 0, double_checked -> False;
    # name, category, quantity, unit, bag, timing, needs_double_check, notes
    # and position all carry. Asserted field by field, because a copy that
    # silently drops one column is a list missing an item.
    ...


def test_a_copy_does_not_carry_the_source_list_s_own_fields(client, db_session):
    # departure_at, saved, template, leg, pair_id, visibility describe THAT
    # list. A template copied with template=True is a second template.
    ...
```

- [ ] **Step 2: Implement.** `PackingListBase` → `PackingListCreate` /
  `PackingListUpdate` / `PackingListResponse`. The router does wiring and status
  mapping only; `copy_items` and the slot functions come from
  `app/services/domain/packing.py`. `visibility` is not settable through the
  API — it ships defaulted and nothing writes it until sharing is built.
- [ ] **Step 3: Document, in this commit** — `docs/api.md` on media's format: a
  table-of-contents bullet, an `## Packing lists — /api/packing-lists` section
  with the `| Method | Path | Auth | Description |` table, and a shared
  conventions section carrying the `204`-on-delete rule and the `409` contract
  once rather than per endpoint.
- [ ] **Step 4: Verify** — full suite under the lock; `ruff check .`
- [ ] **Step 5: Commit** — `feat: the packing list endpoints`

---

### Task 5: The items API

**Files:**
- Create: `app/schemas/packing_item.py`, `app/routers/packing_item.py`
- Create: `tests/api/test_packing_item_router.py`
- Modify: `app/main.py`, `docs/api.md`, `docs/business-rules.md`

```
POST   /api/packing-lists/{list_id}/items   -> 201
PATCH  /api/packing-items/{id}              -> any field
DELETE /api/packing-items/{id}              -> 204
```

- [ ] **Step 1: Write the failing test**

```python
def test_an_unknown_status_is_a_422_not_a_500(client, ...):
    # Rejected by the schema before the CheckConstraint ever sees it. Both
    # layers are asserted: the schema gives a usable error, the constraint is
    # what holds when something writes around the schema.
    ...


def test_a_new_item_goes_to_the_end_of_its_own_list(client, ...):
    # position = max + 1 within the list, not a global counter.
    ...


def test_packing_to_the_target_does_not_flip_the_status_by_itself(client, ...):
    # The count SUGGESTS; the client decides. A server that flipped it would
    # make "three of five is what I'm taking" impossible to express without
    # editing the target.
    ...


def test_an_item_may_be_packed_while_short(client, ...):
    ...


def test_double_checked_is_independent_of_status(client, ...):
    # Packed and still unverified is the state the second field exists for.
    ...
```

- [ ] **Step 2: Implement.** `quantity_packed` above `quantity` is accepted
  without complaint — over-packing is not an error.
- [ ] **Step 3: Document, in this commit** — the endpoint table in `docs/api.md`;
  the count-suggests-status rule in `docs/business-rules.md`.
- [ ] **Step 4: Verify** — full suite under the lock.
- [ ] **Step 5: Commit** — `feat: the packing item endpoints`

---

### Task 6: Common options, learned and prunable

**Files:**
- Create: `app/schemas/label_option.py`, `app/routers/label_option.py`
- Modify: `app/services/domain/packing.py`, `app/main.py`, `docs/api.md`,
  `docs/business-rules.md`
- Create: `tests/api/test_label_option_router.py`

```
GET    /api/label-options?kind=category   -> ordered by position
PATCH  /api/label-options/{id}            -> rename, reorder
DELETE /api/label-options/{id}            -> 204
```

- [ ] **Step 1: Write the failing test**

```python
def test_saving_an_item_records_its_category_as_an_option(client, ...):
    ...


def test_the_same_value_is_not_recorded_twice(client, ...):
    # Unique on (kind, value); the upsert must not raise on the second item
    # that uses the same category.
    ...


def test_renaming_an_option_rewrites_the_items_that_used_it(client, db_session):
    # The item holds text, not a reference. A rename that only touched the
    # option row would leave every existing item on the old value and the
    # screen would show both.
    ...


def test_renaming_onto_an_existing_option_merges(client, db_session):
    # Items are rewritten, then the source row is deleted - the unique
    # constraint would otherwise refuse the rename outright.
    ...


def test_deleting_an_option_leaves_the_items_alone(client, db_session):
    # Pruning a typo from the suggestions must not blank the field on an item
    # legitimately using it. Deleting is about autocomplete, nothing else.
    ...
```

- [ ] **Step 2: Implement.** The upsert runs on item create and on any update
  changing `category` or `bag`. `position` is `max + 1` within the kind.
- [ ] **Step 3: Document, in this commit.**
- [ ] **Step 4: Verify** — full suite under the lock.
- [ ] **Step 5: Commit** — `feat: common options for category and bag`

---

### Task 7: Due-now, and a JS test runner to hold it

The frontend decides what is due, because it is the viewer's calendar day that
matters and the server's is not necessarily the same one. That makes a date
boundary the one piece of frontend logic most likely to be wrong and least
likely to be noticed — off by one on the evening it matters most.

**vitest is media's runner**, configured at `frontend/vitest.config.js` with
tests co-located beside their source. Copy that, including the co-location.

**Files:**
- Create: `frontend/src/lib/timing.js`, `frontend/src/lib/timing.test.js`
- Create: `frontend/vitest.config.js`
- Modify: `frontend/package.json`, `.github/workflows/ci.yml`

**Interfaces:**
- `TIMINGS` — the fixed render order.
- `dueTimings(departureAt, today) -> Set<string>` — pure, both arguments
  explicit so the test is not at the mercy of the clock.

- [ ] **Step 1: Write the failing test**

```js
// The boundaries, which is the whole reason this is a module and not an
// inline ternary. `today` is a parameter for exactly this: a test that reads
// the real clock is a test that fails one day a year.
test('the night before is due when departure is tomorrow', ...)
test('the night before is still due on the day itself', ...)  // <= 1, not == 1
test('nothing is due when the list has no departure date', ...)
test('everything stays due after departure has passed', ...)
```

- [ ] **Step 2: Implement** per the spec's due-when table. `whenever` is always
  in the set — including when `departureAt` is null, where it is the only member
  and nothing is highlighted.
- [ ] **Step 3: Document, in this commit** — the boundary table in
  `docs/business-rules.md`, and the frontend runner in `docs/testing.md`.
- [ ] **Step 4: Verify** — `cd frontend && npm test`, `npm run lint`.
- [ ] **Step 5: Commit** — `test: pin the due-now boundaries`

---

### Task 8: The screens

Media's split decides the fetching: **TanStack Query for anything editable**,
plain fetch for read-only pages. Every screen here is editable, so all of them
go through the query hook. That adds `@tanstack/react-query` to this app, which
is the house convention rather than an invention.

**Files:**
- Modify: `frontend/package.json` (`react-router-dom`, `@tanstack/react-query`)
- Create: `frontend/src/api/client.js`, `frontend/src/api/endpoints.js`,
  `frontend/src/hooks/useApiQuery.js`
- Create: `frontend/src/pages/PackingLists.jsx`,
  `frontend/src/pages/PackingList.jsx`, `frontend/src/pages/Options.jsx`
- Create: `frontend/src/components/ItemRow.jsx`,
  `frontend/src/components/EvictDialog.jsx`
- Modify: `frontend/src/App.jsx`, `frontend/src/index.css`
- Create: `docs/frontend.md`

- [ ] **Step 1: The api layer.** `client.js` is the only place that calls
  `fetch`, and it throws `new Error(data?.detail || ...)` — which is why the
  `409` detail is a string. `endpoints.js` is the URL map.
- [ ] **Step 2: The index screen.** Three sections — recent, saved, templates.
  Creating a list offers the templates and the recent lists to copy from.
- [ ] **Step 3: The eviction dialog.** The `409` is not an error toast: it is a
  dialog naming the list that would be destroyed — from `evict_next` — offering
  **save it instead** as the first action and confirm as the second. A
  destructive confirm whose safe option is missing gets clicked through.
- [ ] **Step 4: The list screen.** Grouped by timing in `TIMINGS` order, due
  groups open and highlighted, the rest collapsed. A grouping toggle
  (timing / category / bag) and a bag filter; timing is the default and is
  restored on reload.
- [ ] **Step 5: The item row.** One-thumb status cycling — tap cycles
  `not_packed → packed → no_need`. Quantity shows as `3 / 5 pairs`, short counts
  marked. An item needing a double-check that has not had one is visibly
  outstanding even when packed; that mark is what the list's completion state
  reads.
- [ ] **Step 6: The options screen.** Rename, reorder, delete, with the rename
  saying how many items it will rewrite.
- [ ] **Step 7: Loading, error and empty states** on media's pattern — a shared
  loading component rather than one per page, and an empty state that offers the
  action that fills it.
- [ ] **Step 8: Mobile first.** Build at 375px and let it widen. This screen is
  used standing over an open suitcase.
- [ ] **Step 9: Verify** — `npm run lint`, `npm test`, `npm run build`, then
  `.\dev.ps1` and work a real list through end to end.
- [ ] **Step 10: Commit** — `feat: the packing list screens`

---

### Task 9: Clear the scaffolding

The documentation has landed task by task. What is left is the rationale that
never belonged in a reference page, and the scaffolding itself.

- [ ] **Step 1: Move the rationale into `docs/notes/decisions.md`** — written as
  it ended up, not as it was designed. Development rarely follows a spec
  exactly, and where the two diverged only what is true now belongs. The
  rejected alternatives are the part worth keeping: one list entity with two
  flags rather than a separate template table; `always` removed; two
  double-check fields rather than a fourth status value; the count suggesting
  rather than setting status.
- [ ] **Step 2: Correct `decisions.md` where it now disagrees, and grep the
  claim rather than the file.** The Module 1 entity list and the "decisions
  behind that shape" prose beneath it both describe `always` and
  `paired_list_id`, hundreds of lines apart. Fixing the one you are looking at
  leaves the other asserting the old thing with equal confidence.
- [ ] **Step 3: Delete the spec and this plan.** Scaffolding does not outlive
  its task; an abandoned spec describes the system as it was imagined in exactly
  the same confident tone as a page that is accurate, and nothing on its face
  says which it is.
- [ ] **Step 4: Merge `dev` in and re-run `alembic heads`** — another session
  could have cut a branch since Task 2, and the collision is silent.
- [ ] **Step 5: Commit** — `docs: record the packing list decisions and clear
  the scaffolding`
- [ ] **Step 6: Open the PR into `dev`** and merge when CI is green. The release
  into `main` is the owner's and is not inferred from this.
