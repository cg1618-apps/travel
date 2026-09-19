# Packing lists — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The first feature in this application — a packing list you can create
from a template, fill in, and work through by when each thing is due, with the
three-list cap enforced and nothing deleted silently.

**Architecture:** Three tables behind a FastAPI router set, and a React screen
whose default grouping is packing timing rather than category. No trips: a list
carries its own nullable departure date, and module 2 adds `trip_id` later.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, Alembic, pytest, React 19
+ Vite, vitest.

**Spec:** `docs/superpowers/specs/2026-09-19-packing-lists.md`. Read it before
Task 2 — every column and every enumerated value is settled there, with the
reasoning. This plan does not restate the "why".

## Global Constraints

- **Ports:** uvicorn 8002, Vite 5175. Unchanged by this plan.
- **One pytest at a time, machine-wide.** Take the lock in the platform
  `CLAUDE.md` before any full run. The new fixtures build a real database; two
  concurrent runs produce failures that look like real breakage.
- **Test fixtures run Alembic. Never `Base.metadata.create_all`.** This is the
  whole reason Task 1 exists and comes first — see its note.
- **No PostgreSQL `ENUM` types.** Enumerated values are text with a
  `CheckConstraint`.
- **No trips, no `/s/...` routes, no share tokens.** `visibility` ships as a
  column and nothing reads it.
- **Nothing in git mentions AI**, in any commit message or pull request body.
- The app stays `status: planned` in the registry. Going live is not this plan.

---

### Task 1: A test database that is built by migrations

Nothing in this suite has ever needed a real schema — the existing tests are
unit tests plus one subprocess run against a scratch database. Every task below
needs a session and a client, so the fixture comes first.

**It runs `alembic upgrade head`, not `Base.metadata.create_all`.** The media
tracker built its fixtures with `create_all` and so ran 145 revisions with a
chain that could not build from nothing — the models were right, the migrations
were wrong, and no test could tell the difference because no test ever ran one.
A fixture is the only place that mistake is invisible.

**Files:**
- Modify: `tests/conftest.py`
- Create: `tests/test_the_fixture_runs_migrations.py`

**Interfaces:**
- Produces: `migrated_database` (session-scoped) — creates `travel_test`, runs
  `alembic upgrade head` against it, yields the URL, drops it `WITH (FORCE)`.
- Produces: `db` (function-scoped) — a `Session` bound to a connection inside a
  transaction that is rolled back on teardown, so tests never see each other's
  rows.
- Produces: `client` (function-scoped) — a `TestClient` with `get_db`
  overridden to that same session.

- [ ] **Step 1: Write the failing test**

```python
"""The fixture's own discipline, asserted rather than assumed.

A fixture that builds its schema with create_all tests the models against
themselves and says nothing about the migrations - which is how the media
tracker shipped 145 revisions on a chain that could not build from zero.
"""

from sqlalchemy import text


def test_the_test_database_is_stamped_at_head(db):
    # create_all leaves no alembic_version row. This assertion is the whole
    # difference between the two ways of building the fixture.
    stamped = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert stamped is not None


def test_a_test_cannot_see_another_test_s_rows(db):
    # Paired with the test below: whichever runs first writes, the other must
    # not find it. Asserts the rollback, which is silent when it fails.
    ...
```

- [ ] **Step 2: Implement**
  - Reuse `_admin_url` from `tests/test_migrations_build_the_schema.py` by
    moving it into `conftest.py` and importing it there, rather than copying
    it. Two copies of the "derive the admin URL from the app's own settings"
    rule is two places to get it wrong.
  - Database name `travel_test`, distinct from that test's
    `travel_migration_test`. They must not share: the from-zero test drops and
    recreates its own, mid-session.
  - The `db` fixture binds the session to an explicit connection with an open
    transaction and rolls back; it does not `DELETE FROM` between tests.
- [ ] **Step 3: Verify** — `venv/Scripts/python.exe -m pytest tests/ -q` under
  the machine-wide lock. The existing suite must still pass unchanged.
- [ ] **Step 4: Commit** — `test: a database fixture built by the migrations`

---

### Task 2: The three tables and the migration

**Files:**
- Create: `app/models/__init__.py`, `app/models/packing.py`
- Create: `alembic/versions/0002_packing.py`
- Create: `tests/test_packing_models.py`

**Interfaces:**
- Produces: `PackingList`, `PackingItem`, `LabelOption` on `app.database.Base`.
- Produces: `Status`, `Timing`, `Leg`, `Visibility`, `LabelKind` as `StrEnum`,
  used for values in Python and stored as plain text.

- [ ] **Step 1: Write the failing test**

```python
"""What the schema itself refuses, and what it cleans up.

These are database-level guarantees, asserted at the database level: a
CheckConstraint that exists only in the model is a constraint the migration
forgot, and every read path would still look correct.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.packing import PackingItem, PackingList


def test_an_unknown_status_is_refused(db):
    db.add(PackingList(name="Tokyo"))
    db.flush()
    ...
    with pytest.raises(IntegrityError):
        db.flush()


def test_deleting_a_list_takes_its_items_with_it(db):
    # ON DELETE CASCADE at the database level, not just cascade= in the
    # relationship: the eviction in Task 3 deletes through the ORM, but a
    # manual DELETE from psql must not leave orphans either.
    ...


def test_quantity_packed_defaults_to_zero_and_quantity_may_be_null(db):
    ...
```

- [ ] **Step 2: Implement the models**
  - Columns exactly as the spec's tables give them. `packing_item.list_id` is
    `ForeignKey("packing_list.id", ondelete="CASCADE")`.
  - `__table_args__` carries the `CheckConstraint`s for `status`, `timing`,
    `leg`, `visibility` and `label_option.kind`, plus the
    `UniqueConstraint("kind", "value")` on `label_option`.
  - Name every constraint explicitly (`ck_packing_item_status`, …). An
    unnamed constraint gets a generated name that Alembic cannot drop in a
    `downgrade`, which turns the rollback hook into a lie.
- [ ] **Step 3: Generate and then read the migration**
  - `alembic revision --autogenerate -m "packing lists"`, then **open the file
    and check it against the models by hand.** Autogenerate does not reliably
    emit `CheckConstraint`s or `ondelete`, and both are load-bearing here.
  - Rename the file to `0002_packing.py` and set `revision = "0002_packing"`,
    `down_revision = "0001_baseline"`, matching the baseline's convention.
  - Write a real `downgrade()` that drops all three tables.
- [ ] **Step 4: Verify**
  - `venv/Scripts/python.exe -m alembic heads` — **exactly one line.** This
    branch adds a revision; anything that landed on `dev` since it was cut
    could have added another, and git merges the two files cleanly while the
    migration tool refuses to run. If there are two, **reparent** — point
    `down_revision` at the new head. Never renumber a revision id.
  - `pytest tests/ -q` under the lock. `test_upgrade_head_runs_against_an_empty_database`
    now has three tables to check and stops being vacuous — that assertion was
    written for this moment.
- [ ] **Step 5: Commit** — `feat: the packing list schema`

---

### Task 3: Slots, and eviction that refuses before it deletes

**Files:**
- Create: `app/services/__init__.py`, `app/services/packing.py`
- Create: `tests/test_slots.py`

**Interfaces:**
- Produces: `count_slots(db) -> int` — distinct `COALESCE(pair_id, id::text)`
  over lists where `saved` is false **and** `template` is false.
- Produces: `oldest_slot(db) -> list[PackingList] | None` — every list in the
  slot with the earliest `created_at`, so a pair comes back as two rows.
- Produces: `evict(db, slot) -> None`.
- Produces: `SLOT_CAP = 3`.

- [ ] **Step 1: Write the failing test**

```python
"""The cap, and the fixture that makes it possible to break.

A cap asserted against an empty database passes because there was nothing to
evict: green on day one, green through the change that breaks it, green
forever. `three_working_lists` is not scene-setting - it is the only reason
the refusal below can fail, and the mirror case uses the same fixture so a
green proves the cap did the refusing and not an empty table.
"""

import pytest

from app.services.packing import SLOT_CAP, count_slots, oldest_slot


@pytest.fixture
def three_working_lists(db):
    """Three lists, neither saved nor templates, oldest first. Load-bearing."""
    ...


def test_three_working_lists_fill_the_cap(three_working_lists, db):
    assert count_slots(db) == SLOT_CAP


def test_two_do_not(three_working_lists, db):
    # The mirror. Same fixture, one list removed: the count must actually move.
    ...


def test_a_round_trip_pair_is_one_slot(db):
    # Two lists sharing a pair_id. Three round trips must fit.
    ...


def test_saved_and_template_lists_do_not_count(three_working_lists, db):
    # Four lists in the table, three slots, because the fourth is saved.
    ...


def test_evicting_a_pair_deletes_both_lists_and_their_items(db):
    ...
```

- [ ] **Step 2: Implement.** `count_slots` is one `SELECT COUNT(DISTINCT ...)`;
  do not load the lists and count in Python, because the same expression is
  reused by `oldest_slot`.
- [ ] **Step 3: Verify** — `pytest tests/test_slots.py -q`, then the full suite
  under the lock.
- [ ] **Step 4: Commit** — `feat: slot counting and eviction for the list cap`

---

### Task 4: The lists API

**Files:**
- Create: `app/schemas/__init__.py`, `app/schemas/packing.py`
- Create: `app/routers/packing_lists.py`
- Modify: `app/main.py` (register the router)
- Create: `tests/test_packing_lists_api.py`

**Interfaces:**

```
GET    /api/packing-lists            -> {recent: [...], saved: [...], templates: [...]}
POST   /api/packing-lists            -> 201 | 409
GET    /api/packing-lists/{id}       -> the list with its items
PATCH  /api/packing-lists/{id}       -> name, departure_at, saved, template, leg, pair_id
DELETE /api/packing-lists/{id}       -> 204
```

`POST` body: `name`, optional `departure_at`, optional `copy_from_id`, optional
`template`/`saved`, optional `evict_confirmed: bool = False`.

- [ ] **Step 1: Write the failing test**

```python
"""Creating a list, copying one, and the refusal that stands between you and
a deleted list.
"""


def test_creating_a_fourth_list_refuses_and_names_what_would_be_destroyed(
    three_working_lists, client
):
    response = client.post("/api/packing-lists", json={"name": "Osaka"})
    assert response.status_code == 409
    # Naming it is the point: a 409 that says only "cap reached" makes the
    # client guess, and the client would guess the wrong list.
    assert response.json()["detail"]["evicts"][0]["name"] == ...


def test_nothing_is_deleted_by_a_refused_create(three_working_lists, client, db):
    ...


def test_confirming_creates_the_list_and_deletes_the_oldest(
    three_working_lists, client, db
):
    ...


def test_three_lists_is_fine_without_confirmation(three_working_lists, client, db):
    # The mirror: delete one of the three first, then a create must be 201
    # with no confirmation and nothing evicted.
    ...


def test_a_copy_carries_the_definition_and_resets_the_state(client, db):
    # status -> not_packed, quantity_packed -> 0, double_checked -> False;
    # name, category, quantity, unit, bag, timing, needs_double_check, notes
    # and position all carry. Asserted field by field, because a copy that
    # silently drops one column is a list missing an item.
    ...


def test_a_copy_does_not_carry_the_source_list_s_own_fields(client, db):
    # departure_at, saved, template, leg, pair_id, visibility describe THAT
    # list. A template copied with template=True is a second template.
    ...
```

- [ ] **Step 2: Implement.**
  - The `409` detail is a dict: `{"reason": "slot_cap", "evicts": [{id, name,
    departure_at}, ...]}`.
  - Copying lives in `app/services/packing.py` as `copy_items(db, source, target)`,
    not in the router — Task 5's item endpoints do not need it, but the spec's
    carry/reset table is one fact and belongs in one function.
  - `visibility` is not settable through the API. It ships defaulted and
    nothing writes it until sharing is built.
- [ ] **Step 3: Verify** — full suite under the lock; `ruff check .`
- [ ] **Step 4: Commit** — `feat: the packing list endpoints`

---

### Task 5: The items API

**Files:**
- Modify: `app/schemas/packing.py`
- Create: `app/routers/packing_items.py`
- Modify: `app/main.py`
- Create: `tests/test_packing_items_api.py`

**Interfaces:**

```
POST   /api/packing-lists/{list_id}/items   -> 201
PATCH  /api/packing-items/{id}              -> any field
DELETE /api/packing-items/{id}              -> 204
```

- [ ] **Step 1: Write the failing test**

```python
def test_an_unknown_status_is_rejected_at_the_edge(client, ...):
    # 422 from the schema, before the CheckConstraint ever sees it. Both
    # layers are asserted: the schema gives a usable error, the constraint
    # is what holds when something writes around the schema.
    ...


def test_a_new_item_goes_to_the_end_of_the_list(client, ...):
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

- [ ] **Step 2: Implement.** Status and timing are `StrEnum` on the pydantic
  schema, which is what produces the 422. `quantity_packed` accepts values
  above `quantity` without complaint — over-packing is not an error.
- [ ] **Step 3: Verify** — full suite under the lock.
- [ ] **Step 4: Commit** — `feat: the packing item endpoints`

---

### Task 6: Common options, learned and prunable

**Files:**
- Modify: `app/services/packing.py` (the upsert)
- Create: `app/routers/label_options.py`
- Modify: `app/main.py`
- Create: `tests/test_label_options.py`

**Interfaces:**

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
    # The unique constraint is on (kind, value); the upsert must not raise
    # on the second item that uses the same category.
    ...


def test_renaming_an_option_rewrites_the_items_that_used_it(client, db):
    # The item holds text, not a reference. A rename that only touched the
    # option row would leave every existing item on the old value and the
    # screen would show both.
    ...


def test_renaming_onto_an_existing_option_merges(client, db):
    # Items are rewritten, then the source row is deleted - the unique
    # constraint would otherwise refuse the rename outright.
    ...


def test_deleting_an_option_leaves_the_items_alone(client, db):
    # Pruning a typo from the suggestions must not blank the field on an item
    # that is legitimately using it. Deleting is about autocomplete, nothing
    # else.
    ...
```

- [ ] **Step 2: Implement.** The upsert runs on item create and on any update
  that changes `category` or `bag`. `position` is `max + 1` within the kind.
- [ ] **Step 3: Verify** — full suite under the lock.
- [ ] **Step 4: Commit** — `feat: common options for category and bag`

---

### Task 7: Due-now, and a JS test runner to hold it

The frontend decides what is due, because it is the viewer's calendar day that
matters and the server's is not necessarily the same one. That makes a date
boundary the one piece of frontend logic most likely to be wrong and least
likely to be noticed — off by one on the evening it matters most.

**This adds vitest**, and it is the only new frontend dependency in this plan
beyond routing. It is Vite's own runner, needs no separate config, and one CI
line runs it. The alternative is an untested boundary in the feature the app
exists for.

**Files:**
- Create: `frontend/src/lib/timing.js`, `frontend/src/lib/timing.test.js`
- Modify: `frontend/package.json` (vitest, `"test": "vitest run"`)
- Modify: `.github/workflows/ci.yml` (run it after `npm run lint`)

**Interfaces:**
- Produces: `TIMINGS` — the fixed render order.
- Produces: `dueTimings(departureAt, today) -> Set<string>` — pure, both
  arguments explicit so the test is not at the mercy of the clock.

- [ ] **Step 1: Write the failing test**

```js
// The boundaries, which is the whole reason this is a module and not an
// inline ternary. `today` is a parameter for exactly this: a test that
// reads the real clock is a test that fails one day a year.
test('the night before is due when departure is tomorrow', ...)
test('the night before is still due on the day itself', ...)  // <= 1, not == 1
test('nothing is due when the list has no departure date', ...)
test('everything stays due after departure has passed', ...)
```

- [ ] **Step 2: Implement** per the spec's due-when table. `whenever` is always
  in the set — including when `departureAt` is null, where it is the only
  member and nothing is highlighted.
- [ ] **Step 3: Verify** — `cd frontend && npm test`, and `npm run lint`.
- [ ] **Step 4: Commit** — `test: pin the due-now boundaries`

---

### Task 8: The screens

**Files:**
- Modify: `frontend/package.json` (react-router-dom)
- Create: `frontend/src/api.js`
- Create: `frontend/src/pages/Lists.jsx`, `frontend/src/pages/ListDetail.jsx`,
  `frontend/src/pages/Options.jsx`
- Create: `frontend/src/components/ItemRow.jsx`, `frontend/src/components/EvictDialog.jsx`
- Modify: `frontend/src/App.jsx`, `frontend/src/index.css`

- [ ] **Step 1: The index screen.** Three sections — recent, saved, templates.
  Creating a list offers the templates and the recent lists to copy from.
- [ ] **Step 2: The eviction dialog.** The `409` is not an error toast: it is a
  dialog naming the list that would be destroyed, offering **save it instead**
  as the first action and confirm as the second. A destructive confirm whose
  safe option is missing gets clicked through.
- [ ] **Step 3: The list screen.** Grouped by timing in `TIMINGS` order, due
  groups open and highlighted, the rest collapsed. A grouping toggle
  (timing / category / bag) and a bag filter; timing is the default and is
  restored on reload.
- [ ] **Step 4: The item row.** One-thumb status cycling — tap cycles
  `not_packed → packed → no_need`. Quantity shows as `3 / 5 pairs`, short
  counts marked. An item needing a double-check that has not had one is
  visibly outstanding even when packed; that mark is what the list's
  completion state reads.
- [ ] **Step 5: The options screen.** Rename, reorder, delete, with the rename
  saying how many items it will rewrite.
- [ ] **Step 6: Mobile first.** Build at 375px and let it widen. This screen is
  used standing over an open suitcase.
- [ ] **Step 7: Verify** — `npm run lint`, `npm test`, `npm run build`, then
  `.\dev.ps1` and work a real list through end to end.
- [ ] **Step 8: Commit** — `feat: the packing list screens`

---

### Task 9: Finish the plan

Both edits in one commit, without being asked. This is the step that gets
skipped.

- [ ] **Step 1: Move what is durable out of the spec**, written as it ended up
  rather than as it was designed:
  - `docs/notes/decisions.md` — the removal of `always`, `pair_id` replacing
    `paired_list_id`, quantity as a target plus a count, the count suggesting
    rather than setting status, single `name` as a deliberate deviation from
    the platform's `name_cn`/`name_en`/`aliases` convention, and the choice of
    CHECK constraints over PostgreSQL enum types. Replace the Module 1 row of
    the structure table's entity sketch where it now disagrees — **grep the
    claim, not the file**: the entity list and the "decisions behind that
    shape" prose both describe `always` and `paired_list_id`, hundreds of
    lines apart.
  - `docs/data-model.md` (new) — the three tables in the present tense.
  - `docs/api.md` (new) — the endpoints, including the `409` contract.
  - `docs/README.md` — add both pages to the table, and delete the paragraph
    saying there is no feature yet.
- [ ] **Step 2: Delete `docs/superpowers/specs/2026-09-19-packing-lists.md` and
  this plan.** Scaffolding does not outlive its task; an abandoned spec
  describes the system as it was imagined in the same confident tone as a page
  that is accurate.
- [ ] **Step 3: Commit** — `docs: record the packing list module and clear the
  scaffolding`
- [ ] **Step 4: Open the PR into `dev`** and merge it when CI is green. The
  release into `main` is the owner's and is not inferred from this.
