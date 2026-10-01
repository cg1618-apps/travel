# Kinds and usage status — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the packing-list cap and the saved/template/archived flags with one `kind` (範本 · 保存 · 一般) plus a `usage` status on 一般 items, where 一般 + 過去使用 is 自動保存 with a limit (5 list slots, 10 trips) — for packing lists and trips alike.

**Architecture:** One Alembic revision moves both tables from booleans to `kind` / `usage` / `auto_saved_at` with check constraints that make impossible combinations unstorable. One domain module, `app/services/domain/auto_save.py`, owns the slot queue and every kind/usage transition for both models; the two routers call it and translate its two exceptions into `422` / `409`. The frontend gets shared label/grouping helpers in `lib/`, and each screen consumes them.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 17, pytest; React 19, TanStack Query, react-router, Tailwind 4, vitest, oxlint.

**Spec:** `docs/superpowers/specs/2026-10-01-usage-status-design.md` — read it first; this plan argues from it.

## Global Constraints

- Stored values are English: `kind` ∈ `template`, `saved`, `free`; `usage` ∈ `in_use`, `upcoming`, `unused`, `past`.
- Display words: 範本 · 保存 · 自動保存 · 一般; 使用中 · 未來使用 · 未使用 · 過去使用; 備註; 保存備註. They live in `frontend/src/lib/labels.js` and nowhere else.
- 封存 / 已封存 / 封存備註 / 設為範本 / 取消範本 disappear from the UI.
- Limits: `AUTO_SAVE_LIMIT` = 5 slots for packing lists (a `pair_id` pair is one slot), 10 for trips (one trip, one slot).
- An API `detail` is English and never rendered.
- Revision id `k1ind0000001`, parent `t3rip0000003` — re-check `alembic heads` before writing it.
- Tests: `venv/Scripts/python.exe -m pytest tests/ -q` under the machine-wide lock (platform `CLAUDE.md`); frontend `npm test`, `npm run lint`, `npm run build` from `frontend/`.
- Commits carry no AI trailers. Stage named files only.

## Review Focus

1. **A pair whose partner is already auto-saved** — setting the second half to 過去使用 adds no slot, so a full queue must not refuse it. Test in Task 2.
2. **Un-saving straight to 過去使用 in one PATCH** (`{"kind": "free", "usage": "past"}`) must go through the limit like any other `past`. Test in Task 2.
3. **Re-sending `usage: past` on an item already past** must not restamp `auto_saved_at` (it would jump the queue) nor be refused when full. Test in Task 2.
4. **Bulk delete with a duplicate id or an empty list** — duplicates are deleted once; `[]` is a `204` that does nothing. Test in Task 4.
5. **The trip on `/trip` changing usage or being saved** — the page must move to `/trips/{id}` rather than show another trip under the click. Pinned by `leavesCurrent` in Task 7.

---

## File map

| File | Change |
| --- | --- |
| `app/constants.py` | + `Kind`, `Usage` |
| `app/models/packing_list.py`, `app/models/trip.py` | flags → `kind`/`usage`/`auto_saved_at`; lists gain `notes`, `archive_note` |
| `alembic/versions/k1ind0000001_kind_and_usage.py` | new revision |
| `app/services/domain/auto_save.py` | **new**: slots, limits, transitions |
| `app/services/domain/packing.py` | cap functions removed |
| `app/services/domain/trip.py` | `current_trip` by usage |
| `app/schemas/packing_list.py`, `app/schemas/trip.py` | new fields, index shapes |
| `app/routers/packing_list.py`, `app/routers/trip.py` | wiring, bulk delete |
| `app/services/sheet_import/write.py` | `saved=` → `kind=` |
| `tests/api/test_auto_save.py` | **new**, replaces `test_slots.py` |
| `tests/api/test_slots.py` | copy tests kept, cap tests removed → renamed `test_copy_items.py` |
| `tests/api/test_packing_list_router.py`, `test_trip_router.py`, `test_trip_copy.py`, `test_packing_models.py` | flags → kind |
| `tests/test_migrations_build_the_schema.py` | + data mapping test |
| `frontend/src/lib/labels.js`, `lib/kinds.js` (**new**), `lib/kinds.test.js` (**new**), `lib/trips.js` | helpers |
| `frontend/src/components/EvictDialog.jsx` | generic wording |
| `frontend/src/components/KindControls.jsx` (**new**) | 狀態 select, 保存 toggle, 當作範本 button |
| `frontend/src/pages/PackingLists.jsx`, `PackingList.jsx`, `Trip.jsx`, `Dashboard.jsx` | consume the above |
| `frontend/src/pages/AutoSavedTrips.jsx` (**new**) | 自動保存的行程 + 刪除模式 |
| `frontend/src/api/endpoints.js`, `App.jsx` | bulk delete, route |
| `docs/*.md` | present-tense pages; spec and plan deleted |

---

### Task 1: Vocabulary, models and the migration

**Files:**
- Modify: `app/constants.py`, `app/models/packing_list.py`, `app/models/trip.py`, `app/services/sheet_import/write.py`
- Create: `alembic/versions/k1ind0000001_kind_and_usage.py`
- Test: `tests/api/test_packing_models.py`, `tests/test_migrations_build_the_schema.py`

**Interfaces:**
- Produces: `Kind` (`TEMPLATE`, `SAVED`, `FREE`), `Usage` (`IN_USE`, `UPCOMING`, `UNUSED`, `PAST`) in `app.constants`; columns `kind`, `usage`, `auto_saved_at` on both models, plus `notes`, `archive_note` on `PackingList`. A model built with no `kind` is `free`/`unused`; one built with `kind=Kind.TEMPLATE` or `Kind.SAVED` has `usage=None`.

- [ ] **Step 1: Write the failing model tests** — append to `tests/api/test_packing_models.py`:

```python
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.constants import Kind, Usage
from app.models import PackingList, Trip


@pytest.mark.parametrize("model", [PackingList, Trip])
def test_a_new_row_is_free_and_unused(db_session, model):
    row = model(name="x")
    db_session.add(row)
    db_session.flush()
    assert (row.kind, row.usage, row.auto_saved_at) == (Kind.FREE, Usage.UNUSED, None)


@pytest.mark.parametrize("model", [PackingList, Trip])
@pytest.mark.parametrize("kind", [Kind.TEMPLATE, Kind.SAVED])
def test_a_template_or_saved_row_has_no_usage(db_session, model, kind):
    row = model(name="x", kind=kind)
    db_session.add(row)
    db_session.flush()
    assert row.usage is None


@pytest.mark.parametrize("model", [PackingList, Trip])
@pytest.mark.parametrize(
    "fields",
    [
        {"kind": Kind.SAVED, "usage": Usage.UNUSED},  # usage on a non-free row
        {"kind": Kind.FREE, "usage": None},  # a free row without usage
        {"kind": Kind.FREE, "usage": Usage.PAST},  # past without auto_saved_at
        {"kind": Kind.FREE, "usage": Usage.UNUSED,
         "auto_saved_at": datetime(2026, 9, 1, tzinfo=timezone.utc)},  # stamp without past
        {"kind": "archived"},  # unknown kind
    ],
)
def test_the_database_refuses_impossible_combinations(db_session, model, fields):
    db_session.add(model(name="x", **fields))
    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize("model", [PackingList, Trip])
def test_a_past_row_with_its_stamp_is_accepted(db_session, model):
    # The mirror of the refusals above: same columns, legal values.
    row = model(name="x", usage=Usage.PAST, auto_saved_at=datetime(2026, 9, 1, tzinfo=timezone.utc))
    db_session.add(row)
    db_session.flush()
    assert row.id is not None


def test_a_list_has_notes_and_an_archive_note(db_session):
    row = PackingList(name="x", notes="帶傘", archive_note="下次少帶")
    db_session.add(row)
    db_session.flush()
    assert (row.notes, row.archive_note) == ("帶傘", "下次少帶")
```

Delete any existing test in that file that constructs `PackingList(saved=...)` / `template=...` (grep `saved\|template`), rewriting it with `kind=` if the behaviour it pins still exists.

- [ ] **Step 2: Run to verify failure**

Run: `venv/Scripts/python.exe -m pytest tests/api/test_packing_models.py -q`
Expected: FAIL — `ImportError: cannot import name 'Kind'`.

- [ ] **Step 3: Add the vocabularies** — append to `app/constants.py` before `TIMING_ORDER`:

```python
class Kind(StrEnum):
    """What sort of list or trip a row is. Shared by both tables.

    自動保存 is deliberately not a member: it is `FREE` with `Usage.PAST`, so
    "a 一般 item marked 過去使用 is auto-saved" holds by construction.
    """

    TEMPLATE = "template"
    SAVED = "saved"
    FREE = "free"


class Usage(StrEnum):
    """Where a 一般 list or trip stands. Only `FREE` rows carry one."""

    IN_USE = "in_use"
    UPCOMING = "upcoming"
    UNUSED = "unused"
    PAST = "past"
```

- [ ] **Step 4: Add the shared columns** — append to `app/models/base.py`:

```python
def _default_usage(context):
    """`unused` for a free row, nothing for a template or a saved one.

    A context-sensitive default because `usage` is required exactly when
    `kind` is free, and a constructor that only names `kind=template` should
    not have to remember to pass `usage=None` as well.
    """
    from app.constants import Kind, Usage

    kind = context.get_current_parameters().get("kind")
    return Usage.UNUSED if kind in (None, Kind.FREE) else None


def kind_constraints(table: str) -> tuple:
    """The four checks that make an impossible kind/usage row unstorable."""
    from sqlalchemy import CheckConstraint

    from app.constants import Kind, Usage

    return (
        CheckConstraint(in_clause("kind", Kind), name=f"ck_{table}_kind"),
        CheckConstraint(in_clause("usage", Usage, nullable=True), name=f"ck_{table}_usage"),
        CheckConstraint("(kind = 'free') = (usage IS NOT NULL)", name=f"ck_{table}_usage_iff_free"),
        CheckConstraint(
            "COALESCE(usage = 'past', false) = (auto_saved_at IS NOT NULL)",
            name=f"ck_{table}_auto_saved_at_iff_past",
        ),
    )


class KindMixin:
    """`kind`, `usage` and `auto_saved_at`, identical on lists and trips."""

    kind: Mapped[str] = mapped_column(String, nullable=False, default="free", server_default="free")
    usage: Mapped[str | None] = mapped_column(String, nullable=True, default=_default_usage)
    #: When the row entered 自動保存; the queue's order. Set iff usage is past.
    auto_saved_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

and add `String` to that file's `from sqlalchemy import ...`.

- [ ] **Step 5: Use them in the models.** In `app/models/packing_list.py`: import `Text` and `KindMixin, kind_constraints`; class becomes `class PackingList(Base, TimestampMixin, KindMixin)`; `__table_args__` gains `*kind_constraints("packing_list")`; delete the `saved` and `template` columns and their comment; add after `departure_at`:

```python
    #: 備註, the planning remark, and 保存備註, the one written afterwards.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    archive_note: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Update the module docstring to `"""A packing list. `kind` and `usage` decide which shelf it is on."""`.

In `app/models/trip.py`: class becomes `class Trip(Base, TimestampMixin, KindMixin)`; `__table_args__` gains `*kind_constraints("trip")`; delete `archived` and `template` and replace their comment with:

```python
    # `archive_note` is 保存備註, the remark written afterwards, kept apart
    # from the planning `notes`. Which shelf the trip is on is `kind`/`usage`.
```

- [ ] **Step 6: Fix the importer** — `app/services/sheet_import/write.py`, `_write_list`:

```python
    row = PackingList(
        name=parsed.name,
        leg=parsed.leg,
        kind=Kind.SAVED if parsed.saved else Kind.FREE,
        pair_id=parsed.pair_id,
    )
```

Import `Kind` from `app.constants` (it already imports `LabelKind` from there).

- [ ] **Step 7: Write the migration** — check `venv/Scripts/alembic.exe heads` prints `t3rip0000003 (head)`; if not, use whatever it prints as `down_revision`. Create `alembic/versions/k1ind0000001_kind_and_usage.py`:

```python
"""lists and trips get a kind and a usage status, replacing their flags

`kind` is template / saved / free; `usage` is set exactly when a row is free;
`auto_saved_at` exactly when usage is past, and orders the 自動保存 queue.
Lists gain the `notes` and `archive_note` trips already have. The booleans go:
a list's `saved` and `template`, a trip's `archived` and `template`.

Downgrade restores the booleans from `kind` and drops the rest - usage
statuses and list remarks are lost.

Revision ID: k1ind0000001
Revises: t3rip0000003
Create Date: 2026-10-01

"""

import sqlalchemy as sa

from alembic import op

revision = "k1ind0000001"
down_revision = "t3rip0000003"
branch_labels = None
depends_on = None

KINDS = "'template', 'saved', 'free'"
USAGES = "'in_use', 'upcoming', 'unused', 'past'"

# The flag that meant 保存 on each table before this revision.
SAVED_FLAG = {"packing_list": "saved", "trip": "archived"}


def _add_kind(table: str) -> None:
    op.add_column(table, sa.Column("kind", sa.String(), server_default="free", nullable=False))
    op.add_column(table, sa.Column("usage", sa.String(), nullable=True))
    op.add_column(table, sa.Column("auto_saved_at", sa.DateTime(timezone=True), nullable=True))
    saved = SAVED_FLAG[table]
    # A row that was both a template and saved/archived becomes a template:
    # templates are never dropped, so nothing is lost.
    op.execute(
        f"UPDATE {table} SET kind = CASE WHEN template THEN 'template' "
        f"WHEN {saved} THEN 'saved' ELSE 'free' END"
    )
    op.execute(f"UPDATE {table} SET usage = 'unused' WHERE kind = 'free'")
    op.drop_column(table, "template")
    op.drop_column(table, saved)
    op.create_check_constraint(f"ck_{table}_kind", table, f"kind IN ({KINDS})")
    op.create_check_constraint(f"ck_{table}_usage", table, f"usage IS NULL OR usage IN ({USAGES})")
    op.create_check_constraint(
        f"ck_{table}_usage_iff_free", table, "(kind = 'free') = (usage IS NOT NULL)"
    )
    op.create_check_constraint(
        f"ck_{table}_auto_saved_at_iff_past",
        table,
        "COALESCE(usage = 'past', false) = (auto_saved_at IS NOT NULL)",
    )


def _drop_kind(table: str) -> None:
    saved = SAVED_FLAG[table]
    for name in ("auto_saved_at_iff_past", "usage_iff_free", "usage", "kind"):
        op.drop_constraint(f"ck_{table}_{name}", table, type_="check")
    op.add_column(table, sa.Column(saved, sa.Boolean(), server_default="false", nullable=False))
    op.add_column(table, sa.Column("template", sa.Boolean(), server_default="false", nullable=False))
    op.execute(f"UPDATE {table} SET template = (kind = 'template'), {saved} = (kind = 'saved')")
    op.drop_column(table, "auto_saved_at")
    op.drop_column(table, "usage")
    op.drop_column(table, "kind")


def upgrade() -> None:
    _add_kind("packing_list")
    _add_kind("trip")
    op.add_column("packing_list", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("packing_list", sa.Column("archive_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("packing_list", "archive_note")
    op.drop_column("packing_list", "notes")
    _drop_kind("trip")
    _drop_kind("packing_list")
```

- [ ] **Step 8: Write the data-mapping test** — append to `tests/test_migrations_build_the_schema.py` (it owns `scratch_database`):

```python
def test_the_kind_revision_maps_every_flag_combination_and_back(scratch_database):
    """Load-bearing seed: on an empty database the UPDATEs meet nothing and a
    wrong CASE would still pass. One row per row of the spec's mapping table."""
    env = {**os.environ, "DATABASE_URL": scratch_database}

    def alembic(*command):
        result = subprocess.run([sys.executable, "-m", "alembic", *command], cwd=ROOT,
                                env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

    alembic("upgrade", "t3rip0000003")
    engine = create_engine(scratch_database)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO packing_list (name, saved, template) VALUES "
            "('both', true, true), ('tpl', false, true), ('kept', true, false), ('plain', false, false)"
        ))
        conn.execute(text(
            "INSERT INTO trip (name, archived, template, archive_note) VALUES "
            "('both', true, true, null), ('tpl', false, true, null), "
            "('old', true, false, '早點訂'), ('plain', false, false, null)"
        ))

    alembic("upgrade", "k1ind0000001")
    expected = {"both": ("template", None), "tpl": ("template", None),
                "kept": ("saved", None), "plain": ("free", "unused"),
                "old": ("saved", None)}
    with engine.connect() as conn:
        for table in ("packing_list", "trip"):
            rows = conn.execute(text(f"SELECT name, kind, usage FROM {table}")).all()
            for name, kind, usage in rows:
                assert (kind, usage) == expected[name], (table, name)
        note = conn.execute(text("SELECT archive_note FROM trip WHERE name = 'old'")).scalar()
        assert note == "早點訂"

    alembic("downgrade", "t3rip0000003")
    with engine.connect() as conn:
        lists = dict(conn.execute(text("SELECT name, (saved, template)::text FROM packing_list")).all())
        trips = dict(conn.execute(text("SELECT name, (archived, template)::text FROM trip")).all())
    engine.dispose()
    # `both` comes back a template only: the 保存 half was not kept.
    assert lists == {"both": "(f,t)", "tpl": "(f,t)", "kept": "(t,f)", "plain": "(f,f)"}
    assert trips == {"both": "(f,t)", "tpl": "(f,t)", "old": "(t,f)", "plain": "(f,f)"}
```

- [ ] **Step 9: Run the task's tests (take the lock)**

Run: `venv/Scripts/python.exe -m pytest tests/api/test_packing_models.py tests/test_migrations_build_the_schema.py -q`
Expected: PASS. (Router tests will fail until Tasks 2–4; that is expected and why this task does not run the whole suite.)

- [ ] **Step 10: Commit**

```bash
git add app/constants.py app/models/base.py app/models/packing_list.py app/models/trip.py \
  app/services/sheet_import/write.py alembic/versions/k1ind0000001_kind_and_usage.py \
  tests/api/test_packing_models.py tests/test_migrations_build_the_schema.py
git commit -m "feat: lists and trips get a kind and a usage status in place of their flags"
```

---

### Task 2: The auto-save queue and every transition

**Files:**
- Create: `app/services/domain/auto_save.py`, `tests/api/test_auto_save.py`
- Modify: `app/services/domain/packing.py` (remove `SLOT_CAP`, `SLOT_KEY`, `_WORKING`, `count_slots`, `oldest_slot`, `evict`); `tests/api/test_slots.py` → `git mv` to `tests/api/test_copy_items.py`, keeping only the three copy tests and `make_list`

**Interfaces:**
- Consumes: `Kind`, `Usage`, `KindMixin` columns (Task 1).
- Produces, in `app.services.domain.auto_save`:
  - `AUTO_SAVE_LIMIT: dict[type, int]` — `{PackingList: 5, Trip: 10}`
  - `count_slots(db, model) -> int`
  - `oldest_slot(db, model) -> list[row]` — rows ordered by `id`; `[]` when empty
  - `evict_next(db, model) -> list[row]` — `oldest_slot` when full, else `[]`
  - `class KindRefused(ValueError)` — message is the `422` detail
  - `class AutoSaveFull(Exception)` — `.slot: list[row]`
  - `apply_kind(db, row, changes: dict, *, confirmed: bool, now: datetime) -> None` — pops `kind`/`usage` from `changes` and applies them; raises the two above.

- [ ] **Step 1: Write the failing tests** — `tests/api/test_auto_save.py`:

```python
"""The 自動保存 queue: slots, the limit, and every kind/usage move.

**A limit asserted against an empty queue passes because there was nothing to
drop.** `full_lists` and `full_trips` fill the queue to the limit and are the
only reason any refusal here can fail; each refusal has a mirror one under the
limit using the same rows. `auto_saved_at` is set explicitly: `now()` is the
transaction's start, so rows made in one test would otherwise tie.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.constants import Kind, Usage
from app.models import PackingItem, PackingList, Trip
from app.services.domain.auto_save import (
    AUTO_SAVE_LIMIT,
    AutoSaveFull,
    KindRefused,
    apply_kind,
    count_slots,
    evict_next,
    oldest_slot,
)

EPOCH = datetime(2026, 9, 1, tzinfo=timezone.utc)
NOW = EPOCH + timedelta(days=100)


def past(db, model, name, day, **fields):
    row = model(name=name, usage=Usage.PAST, auto_saved_at=EPOCH + timedelta(days=day), **fields)
    db.add(row)
    db.flush()
    return row


def free(db, model, name="new", **fields):
    row = model(name=name, **fields)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def full_lists(db_session):
    """Five auto-saved list slots, oldest first. Load-bearing."""
    return [past(db_session, PackingList, f"L{day}", day) for day in range(AUTO_SAVE_LIMIT[PackingList])]


@pytest.fixture
def full_trips(db_session):
    """Ten auto-saved trips, oldest first. Load-bearing."""
    return [past(db_session, Trip, f"T{day}", day) for day in range(AUTO_SAVE_LIMIT[Trip])]


# --- slots -------------------------------------------------------------------


def test_the_limits_are_five_lists_and_ten_trips():
    assert AUTO_SAVE_LIMIT == {PackingList: 5, Trip: 10}


@pytest.mark.parametrize("model", [PackingList, Trip])
def test_only_free_past_rows_occupy_slots(db_session, model):
    free(db_session, model)
    free(db_session, model, kind=Kind.SAVED)
    free(db_session, model, kind=Kind.TEMPLATE)
    assert count_slots(db_session, model) == 0
    past(db_session, model, "p", 0)
    assert count_slots(db_session, model) == 1


def test_a_list_pair_is_one_slot(db_session):
    past(db_session, PackingList, "去", 0, pair_id="p")
    past(db_session, PackingList, "回", 1, pair_id="p")
    assert count_slots(db_session, PackingList) == 1


def test_the_oldest_slot_ties_break_on_id(db_session):
    first = past(db_session, Trip, "a", 0)
    past(db_session, Trip, "b", 0)
    assert [row.id for row in oldest_slot(db_session, Trip)] == [first.id]


def test_the_oldest_pair_slot_holds_only_its_auto_saved_halves(db_session):
    gone = past(db_session, PackingList, "去", 0, pair_id="p")
    kept = free(db_session, PackingList, "回", pair_id="p", usage=Usage.IN_USE)
    assert oldest_slot(db_session, PackingList) == [gone]
    assert kept not in oldest_slot(db_session, PackingList)


def test_evict_next_is_empty_until_full(full_lists, db_session):
    assert [row.name for row in evict_next(db_session, PackingList)] == ["L0"]
    db_session.delete(full_lists[-1])
    db_session.flush()
    assert evict_next(db_session, PackingList) == []  # mirror


# --- setting past -------------------------------------------------------------


@pytest.mark.parametrize("model,fixture", [(PackingList, "full_lists"), (Trip, "full_trips")])
def test_past_when_full_is_refused_naming_the_oldest(request, db_session, model, fixture):
    rows = request.getfixturevalue(fixture)
    row = free(db_session, model)
    with pytest.raises(AutoSaveFull) as refused:
        apply_kind(db_session, row, {"usage": Usage.PAST}, confirmed=False, now=NOW)
    assert refused.value.slot == [rows[0]]
    assert row.usage == Usage.UNUSED  # nothing changed


@pytest.mark.parametrize("model,fixture", [(PackingList, "full_lists"), (Trip, "full_trips")])
def test_past_when_full_and_confirmed_drops_the_oldest(request, db_session, model, fixture):
    rows = request.getfixturevalue(fixture)
    oldest_id = rows[0].id
    row = free(db_session, model)
    apply_kind(db_session, row, {"usage": Usage.PAST}, confirmed=True, now=NOW)
    db_session.flush()
    assert db_session.get(model, oldest_id) is None
    assert (row.usage, row.auto_saved_at) == (Usage.PAST, NOW)
    assert count_slots(db_session, model) == AUTO_SAVE_LIMIT[model]


@pytest.mark.parametrize("model,fixture", [(PackingList, "full_lists"), (Trip, "full_trips")])
def test_past_under_the_limit_is_not_refused(request, db_session, model, fixture):
    rows = request.getfixturevalue(fixture)
    db_session.delete(rows[-1])
    db_session.flush()
    row = free(db_session, model)
    apply_kind(db_session, row, {"usage": Usage.PAST}, confirmed=False, now=NOW)
    assert row.auto_saved_at == NOW


def test_a_dropped_list_takes_its_items(full_lists, db_session):
    full_lists[0].items.append(PackingItem(name="傘", position=0))
    db_session.flush()
    item_id = full_lists[0].items[0].id
    apply_kind(db_session, free(db_session, PackingList), {"usage": Usage.PAST}, confirmed=True, now=NOW)
    db_session.flush()
    db_session.expire_all()
    assert db_session.get(PackingItem, item_id) is None


def test_the_second_half_of_a_pair_adds_no_slot(full_lists, db_session):
    full_lists[-1].pair_id = "p"
    other_half = free(db_session, PackingList, "回", pair_id="p")
    apply_kind(db_session, other_half, {"usage": Usage.PAST}, confirmed=False, now=NOW)
    assert other_half.usage == Usage.PAST


def test_resending_past_keeps_the_stamp_and_is_not_refused(full_lists, db_session):
    row = full_lists[2]
    stamp = row.auto_saved_at
    apply_kind(db_session, row, {"usage": Usage.PAST}, confirmed=False, now=NOW)
    assert row.auto_saved_at == stamp


@pytest.mark.parametrize("usage", [Usage.IN_USE, Usage.UPCOMING, Usage.UNUSED])
def test_leaving_past_clears_the_stamp(db_session, usage):
    row = past(db_session, Trip, "p", 0)
    apply_kind(db_session, row, {"usage": usage}, confirmed=False, now=NOW)
    assert (row.usage, row.auto_saved_at) == (usage, None)


# --- 保存 and 取消保存 -----------------------------------------------------------


@pytest.mark.parametrize("model", [PackingList, Trip])
def test_saving_a_free_or_auto_saved_row_clears_usage(db_session, model):
    for row in (free(db_session, model), past(db_session, model, "p", 0)):
        apply_kind(db_session, row, {"kind": Kind.SAVED}, confirmed=False, now=NOW)
        assert (row.kind, row.usage, row.auto_saved_at) == (Kind.SAVED, None, None)


def test_saving_is_never_refused_by_the_limit(full_lists, db_session):
    apply_kind(db_session, full_lists[0], {"kind": Kind.SAVED}, confirmed=False, now=NOW)
    assert full_lists[0].kind == Kind.SAVED


def test_unsaving_returns_a_row_to_free_unused(db_session):
    row = free(db_session, PackingList, kind=Kind.SAVED)
    apply_kind(db_session, row, {"kind": Kind.FREE}, confirmed=False, now=NOW)
    assert (row.kind, row.usage) == (Kind.FREE, Usage.UNUSED)


def test_unsaving_straight_to_past_goes_through_the_limit(full_lists, db_session):
    row = free(db_session, PackingList, kind=Kind.SAVED)
    with pytest.raises(AutoSaveFull):
        apply_kind(db_session, row, {"kind": Kind.FREE, "usage": Usage.PAST}, confirmed=False, now=NOW)
    assert row.kind == Kind.SAVED


# --- refusals ------------------------------------------------------------------


@pytest.mark.parametrize(
    "start,changes",
    [
        ({"kind": Kind.FREE}, {"kind": Kind.TEMPLATE}),
        ({"kind": Kind.TEMPLATE}, {"kind": Kind.SAVED}),
        ({"kind": Kind.TEMPLATE}, {"usage": Usage.IN_USE}),
        ({"kind": Kind.SAVED}, {"usage": Usage.IN_USE}),
    ],
)
def test_impossible_moves_are_refused(db_session, start, changes):
    row = free(db_session, Trip, **start)
    with pytest.raises(KindRefused):
        apply_kind(db_session, row, dict(changes), confirmed=False, now=NOW)


def test_a_free_row_may_change_usage(db_session):
    # Mirror of the refusal above for `usage` on a saved row.
    row = free(db_session, Trip)
    apply_kind(db_session, row, {"usage": Usage.IN_USE}, confirmed=False, now=NOW)
    assert row.usage == Usage.IN_USE
```

- [ ] **Step 2: Run to verify failure**

Run: `venv/Scripts/python.exe -m pytest tests/api/test_auto_save.py -q`
Expected: FAIL — `ModuleNotFoundError: app.services.domain.auto_save`.

- [ ] **Step 3: Implement** — `app/services/domain/auto_save.py`:

```python
"""The 自動保存 queue and every move between kinds, for lists and trips.

自動保存 is a 一般 row whose usage is 過去使用. The queue is capped - five list
slots, ten trips - and the oldest slot is dropped to make room, but never
silently: the first attempt raises `AutoSaveFull` naming what would go, and
only a confirmed retry drops it.

Nothing here raises `HTTPException`; the routers decide what a refusal looks
like over HTTP.
"""

from datetime import datetime

from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from app.constants import Kind, Usage
from app.models import PackingList, Trip

AUTO_SAVE_LIMIT: dict[type, int] = {PackingList: 5, Trip: 10}


class KindRefused(ValueError):
    """A move the model does not allow. The message is the 422's detail."""


class AutoSaveFull(Exception):
    """Setting 過去使用 would overflow the queue. `slot` is what would go."""

    def __init__(self, slot: list):
        super().__init__("auto-save is full")
        self.slot = slot


def _slot_key(model):
    """A round-trip pair of lists is one slot; every trip is its own."""
    if model is PackingList:
        return func.coalesce(PackingList.pair_id, cast(PackingList.id, String))
    return cast(model.id, String)


def _auto_saved(model):
    return (model.kind == Kind.FREE, model.usage == Usage.PAST)


def count_slots(db: Session, model) -> int:
    key = _slot_key(model)
    return db.execute(select(func.count(func.distinct(key))).where(*_auto_saved(model))).scalar_one()


def oldest_slot(db: Session, model) -> list:
    """The auto-saved rows of the slot that would be dropped next.

    Ordered by the slot's earliest `auto_saved_at`, then its lowest id - the
    tie-break is load-bearing, since `now()` is the transaction's start. Only
    the auto-saved halves of a pair come back: a half still 使用中 is not
    part of the queue and is not dropped with it.
    """
    key = _slot_key(model)
    slot = db.execute(
        select(key.label("slot"), func.min(model.auto_saved_at).label("at"), func.min(model.id).label("id"))
        .where(*_auto_saved(model))
        .group_by(key)
        .order_by("at", "id")
        .limit(1)
    ).first()
    if slot is None:
        return []
    return list(
        db.execute(select(model).where(*_auto_saved(model), key == slot.slot).order_by(model.id))
        .scalars()
        .all()
    )


def evict_next(db: Session, model) -> list:
    """What the next 過去使用 would drop, or nothing while there is room."""
    if count_slots(db, model) < AUTO_SAVE_LIMIT[model]:
        return []
    return oldest_slot(db, model)


def _adds_slot(db: Session, row) -> bool:
    """Whether `row` entering the queue would take a slot it does not share.

    The second half of a pair whose first half is already auto-saved joins
    that slot, so a full queue must not refuse it.
    """
    if not isinstance(row, PackingList) or row.pair_id is None:
        return True
    partner = db.execute(
        select(PackingList.id).where(
            *_auto_saved(PackingList), PackingList.pair_id == row.pair_id, PackingList.id != row.id
        )
    ).first()
    return partner is None


def _enter_queue(db: Session, row, *, confirmed: bool, now: datetime) -> None:
    model = type(row)
    if _adds_slot(db, row) and count_slots(db, model) >= AUTO_SAVE_LIMIT[model]:
        slot = oldest_slot(db, model)
        if not confirmed:
            raise AutoSaveFull(slot)
        for dropped in slot:
            db.delete(dropped)
        db.flush()
    row.auto_saved_at = now


def apply_kind(db: Session, row, changes: dict, *, confirmed: bool, now: datetime) -> None:
    """Apply a PATCH's `kind` and `usage` to `row`, popping them from `changes`.

    Every check runs before anything is written, so a refusal leaves the row
    as it was.
    """
    kind = changes.pop("kind", None)
    usage = changes.pop("usage", None)
    if kind is None and usage is None:
        return
    if row.kind == Kind.TEMPLATE:
        raise KindRefused("A template's kind and usage cannot change.")
    if kind == Kind.TEMPLATE:
        raise KindRefused("A list or trip becomes a template only by creating one.")

    target_kind = kind or row.kind
    if usage is not None and target_kind != Kind.FREE:
        raise KindRefused("Only a free list or trip has a usage.")

    if target_kind == Kind.SAVED:
        row.kind, row.usage, row.auto_saved_at = Kind.SAVED, None, None
        return

    current = row.usage if row.kind == Kind.FREE else Usage.UNUSED
    target_usage = usage or current
    if target_usage == Usage.PAST and current != Usage.PAST:
        _enter_queue(db, row, confirmed=confirmed, now=now)
    elif target_usage != Usage.PAST:
        row.auto_saved_at = None
    row.kind, row.usage = Kind.FREE, target_usage
```

Note the ordering for `_enter_queue`: it sets `auto_saved_at` before `usage` is assigned; both land in the same flush, which the `auto_saved_at_iff_past` check sees together.

- [ ] **Step 4: Remove the old cap from `packing.py`** — delete `SLOT_CAP`, `SLOT_KEY`, `_WORKING`, `count_slots`, `oldest_slot`, `evict`, the `String, cast, func, select` imports they used (keep `update`), and change the module docstring's first line to `"""The rules about a list's contents: what a copy carries, where a variant goes, what a reset clears.`. In `copy_items`' docstring replace `departure_at, saved, template, leg, pair_id, visibility` with `departure_at, kind, usage, leg, pair_id, notes, archive_note, visibility`.

- [ ] **Step 5: Keep the copy tests** — `git mv tests/api/test_slots.py tests/api/test_copy_items.py`; in it delete the module docstring's cap paragraph, the `three_working_lists` fixture, every `test_*` from `test_three_working_lists_fill_the_cap` to `test_evicting_leaves_every_other_slot_alone`, and the imports of the removed names. Keep `make_list` and the three `copy` tests. New docstring: `"""What a copy carries, and what it resets."""`.

- [ ] **Step 6: Run**

Run: `venv/Scripts/python.exe -m pytest tests/api/test_auto_save.py tests/api/test_copy_items.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/services/domain/auto_save.py app/services/domain/packing.py \
  tests/api/test_auto_save.py tests/api/test_copy_items.py tests/api/test_slots.py
git commit -m "feat: the auto-save queue and every move between kinds"
```

---

### Task 3: Packing-list API

**Files:**
- Modify: `app/schemas/packing_list.py`, `app/routers/packing_list.py`, `tests/api/test_packing_list_router.py`, `tests/api/test_trip_router.py` and `tests/api/test_trip_copy.py` (only their `"saved": True` list payloads)

**Interfaces:**
- Consumes: `apply_kind`, `evict_next`, `AutoSaveFull`, `KindRefused` (Task 2).
- Produces: `GET /api/packing-lists` → `{free, auto_saved, saved, templates, evict_next}`; summaries and reads carry `kind`, `usage`, `auto_saved_at`, `notes`, `archive_note`; `POST` takes `kind` (`free`|`template`), no `evict_confirmed`; `PATCH` takes `kind` (`saved`|`free`), `usage`, `notes`, `archive_note`, `evict_confirmed`.

- [ ] **Step 1: Rewrite the router tests.** In `tests/api/test_packing_list_router.py` delete `three_working_lists` and every test from `test_creating_a_fourth_list_refuses_and_names_what_would_be_destroyed` through `test_the_index_offers_nothing_to_evict_when_there_is_room`, and `test_a_failed_copy_does_not_cost_you_the_oldest_list`. Replace any `saved=True`/`template=True` construction in the remaining tests with `kind=Kind.SAVED`/`kind=Kind.TEMPLATE`, and change `test_a_copy_does_not_carry_the_source_list_s_own_fields` to assert the copy is `kind == "free"`, `usage == "unused"`, `notes is None`, `archive_note is None` from a template source with notes. Add:

```python
from app.constants import Kind, Usage

FULL = datetime(2026, 9, 1, tzinfo=timezone.utc)


@pytest.fixture
def five_auto_saved(db_session):
    """The queue at its limit. Load-bearing: without it no refusal can fail."""
    rows = [
        make_list(db_session, f"L{day}", usage=Usage.PAST, auto_saved_at=FULL + timedelta(days=day))
        for day in range(5)
    ]
    db_session.commit()
    return rows


def test_a_new_list_is_free_and_unused(client):
    body = client.post("/api/packing-lists", json={"name": "Osaka"}).json()
    assert (body["kind"], body["usage"], body["auto_saved_at"]) == ("free", "unused", None)


def test_a_template_can_be_created_blank_or_copied(client, db_session):
    source = make_list(db_session, "札幌", notes="冬天")
    db_session.add(PackingItem(list_id=source.id, name="傘", position=0))
    db_session.commit()
    blank = client.post("/api/packing-lists", json={"name": "空", "kind": "template"}).json()
    copy = client.post("/api/packing-lists",
                       json={"name": "札幌（範本）", "kind": "template", "copy_from_id": source.id}).json()
    assert (blank["kind"], blank["usage"]) == ("template", None)
    assert [item["name"] for item in copy["items"]] == ["傘"]
    assert db_session.get(PackingList, source.id).kind == Kind.FREE  # the original stays


def test_a_list_cannot_be_created_saved(client):
    assert client.post("/api/packing-lists", json={"name": "x", "kind": "saved"}).status_code == 422


def test_creating_is_never_refused_by_the_queue(five_auto_saved, client):
    assert client.post("/api/packing-lists", json={"name": "x"}).status_code == 201


def test_the_index_has_four_shelves(client, db_session):
    make_list(db_session, "free")
    make_list(db_session, "auto", usage=Usage.PAST, auto_saved_at=FULL)
    make_list(db_session, "kept", kind=Kind.SAVED)
    make_list(db_session, "tpl", kind=Kind.TEMPLATE)
    db_session.commit()
    body = client.get("/api/packing-lists").json()
    shelves = {name: [row["name"] for row in body[name]]
               for name in ("free", "auto_saved", "saved", "templates")}
    assert shelves == {"free": ["free"], "auto_saved": ["auto"], "saved": ["kept"], "templates": ["tpl"]}
    assert body["evict_next"] == []


def test_auto_saved_is_newest_first(client, db_session):
    make_list(db_session, "older", usage=Usage.PAST, auto_saved_at=FULL)
    make_list(db_session, "newer", usage=Usage.PAST, auto_saved_at=FULL + timedelta(days=1))
    db_session.commit()
    body = client.get("/api/packing-lists").json()
    assert [row["name"] for row in body["auto_saved"]] == ["newer", "older"]


def test_past_when_full_is_a_409_and_changes_nothing(five_auto_saved, client, db_session):
    target = make_list(db_session, "new")
    db_session.commit()
    assert client.get("/api/packing-lists").json()["evict_next"][0]["name"] == "L0"
    refused = client.patch(f"/api/packing-lists/{target.id}", json={"usage": "past"})
    assert refused.status_code == 409
    assert "L0" in refused.json()["detail"]
    db_session.expire_all()
    assert db_session.get(PackingList, five_auto_saved[0].id) is not None
    assert db_session.get(PackingList, target.id).usage == Usage.UNUSED


def test_past_when_full_and_confirmed_drops_the_oldest(five_auto_saved, client, db_session):
    target = make_list(db_session, "new")
    oldest = five_auto_saved[0].id
    db_session.commit()
    body = client.patch(f"/api/packing-lists/{target.id}",
                        json={"usage": "past", "evict_confirmed": True}).json()
    assert body["usage"] == "past"
    db_session.expire_all()
    assert db_session.get(PackingList, oldest) is None


def test_saving_and_unsaving(client, db_session):
    target = make_list(db_session, "x", usage=Usage.IN_USE)
    db_session.commit()
    url = f"/api/packing-lists/{target.id}"
    assert client.patch(url, json={"kind": "saved"}).json()["usage"] is None
    body = client.patch(url, json={"kind": "free"}).json()
    assert (body["kind"], body["usage"]) == ("free", "unused")


@pytest.mark.parametrize(
    "start,payload",
    [({"kind": Kind.FREE}, {"kind": "template"}),
     ({"kind": Kind.TEMPLATE}, {"kind": "saved"}),
     ({"kind": Kind.SAVED}, {"usage": "in_use"})],
)
def test_impossible_moves_are_a_422(client, db_session, start, payload):
    target = make_list(db_session, "x", **start)
    db_session.commit()
    assert client.patch(f"/api/packing-lists/{target.id}", json=payload).status_code == 422


@pytest.mark.parametrize("field", ["kind", "usage"])
def test_a_null_kind_or_usage_is_a_422(client, db_session, field):
    target = make_list(db_session, "x")
    db_session.commit()
    assert client.patch(f"/api/packing-lists/{target.id}", json={field: None}).status_code == 422


def test_notes_and_archive_note_are_editable(client, db_session):
    target = make_list(db_session, "x")
    db_session.commit()
    body = client.patch(f"/api/packing-lists/{target.id}",
                        json={"notes": "帶傘", "archive_note": "下次少帶"}).json()
    assert (body["notes"], body["archive_note"]) == ("帶傘", "下次少帶")
```

`make_list` passes `**overrides` to `PackingList`, so `usage=`/`auto_saved_at=`/`kind=`/`notes=` work as written. In `test_a_null_for_a_required_list_field_is_a_422`, change its parametrisation from `saved`/`template` to `kind`/`usage` if it lists them. In `tests/api/test_trip_router.py` and `tests/api/test_trip_copy.py`, replace every packing-list payload `"saved": True` with `"kind": "template"` (the tests only need a list that exists).

- [ ] **Step 2: Run to verify failure**

Run: `venv/Scripts/python.exe -m pytest tests/api/test_packing_list_router.py -q`
Expected: FAIL (unknown `kind` field, missing `free` shelf).

- [ ] **Step 3: Schemas** — replace `app/schemas/packing_list.py` from `class PackingListBase` through `class PackingListUpdate` and the `saved`/`template` fields of `PackingListFields`, and the index:

```python
class PackingListBase(BaseModel):
    name: str = Field(min_length=1)
    departure_at: date | None = None
    leg: Leg | None = None
    pair_id: str | None = None
    notes: str | None = None
    archive_note: str | None = None


class PackingListCreate(PackingListBase):
    #: 一般 by default; `template` makes a 範本 - blank, or 當作範本 with
    #: `copy_from_id`. Nothing is created saved: saving is a move.
    kind: Literal["free", "template"] = "free"

    #: Copy the items of an existing list, of any kind.
    copy_from_id: int | None = None


class PackingListUpdate(NonNullableUpdate):
    # `evict_confirmed` is not a column, and is a plain bool, so it needs no
    # entry: pydantic already refuses null for it.
    non_nullable = ("name", "kind", "usage")

    name: str | None = Field(default=None, min_length=1)
    departure_at: date | None = None
    #: 保存 or 取消保存. A template is made by creating one.
    kind: Literal["saved", "free"] | None = None
    usage: Usage | None = None
    leg: Leg | None = None
    pair_id: str | None = None
    notes: str | None = None
    archive_note: str | None = None
    #: Acknowledges that 過去使用 may drop the oldest 自動保存 slot.
    evict_confirmed: bool = False
```

In `PackingListFields` replace `saved: bool` / `template: bool` with:

```python
    kind: Kind
    usage: Usage | None
    auto_saved_at: datetime | None
    notes: str | None
    archive_note: str | None
```

Replace `PackingListIndex`:

```python
class PackingListIndex(BaseModel):
    """The four shelves, and what the next 過去使用 would drop.

    `evict_next` carries what a 409 cannot: the refusal's `detail` is a plain
    string, and the dialog needs ids to offer 保存 instead.
    """

    free: list[PackingListSummary]
    auto_saved: list[PackingListSummary]
    saved: list[PackingListSummary]
    templates: list[PackingListSummary]
    evict_next: list[PackingListSummary]
```

Imports: `from datetime import date, datetime`; `from app.constants import Kind, Leg, Usage`.

- [ ] **Step 4: Router** — in `app/routers/packing_list.py` replace the docstring's first line with `"""Packing lists: the four shelves, creating one, and the queue that refuses.`; replace the `packing` import with `from app.services.domain.packing import copy_items, reset_list` and add `from app.services.domain.auto_save import AutoSaveFull, KindRefused, apply_kind, evict_next`, `from datetime import datetime, timezone`, `from app.constants import Kind, Status, Usage`. Delete `_refusal` and `_make_room`; add:

```python
def _refusal(slot: list[PackingList]) -> str:
    """A plain string naming what would go; the ids come from `evict_next`."""
    names = " and ".join(f'"{packing_list.name}"' for packing_list in slot)
    return (
        f"Auto-save already holds 5 lists. Marking this one past would delete "
        f"{names}, the oldest. Save it first if you want to keep it, or confirm "
        f"to replace it."
    )
```

Replace `index`'s body after the query:

```python
    def shelf(predicate):
        return [_summary(row) for row in lists if predicate(row)]

    auto_saved = sorted(
        (row for row in lists if row.kind == Kind.FREE and row.usage == Usage.PAST),
        key=lambda row: (row.auto_saved_at, row.id),
        reverse=True,
    )
    return PackingListIndex(
        free=shelf(lambda row: row.kind == Kind.FREE and row.usage != Usage.PAST),
        auto_saved=[_summary(row) for row in auto_saved],
        saved=shelf(lambda row: row.kind == Kind.SAVED),
        templates=shelf(lambda row: row.kind == Kind.TEMPLATE),
        evict_next=[_summary(row) for row in evict_next(db, PackingList)],
    )
```

In `create`, delete the `_make_room` call and its comment, and change the dump to `PackingList(**payload.model_dump(exclude={"copy_from_id"}))`.

Replace `update`'s body:

```python
    packing_list = _get(db, list_id)
    changes = payload.model_dump(exclude_unset=True, exclude={"evict_confirmed"})
    try:
        apply_kind(db, packing_list, changes, confirmed=payload.evict_confirmed,
                   now=datetime.now(timezone.utc))
    except KindRefused as refused:
        raise HTTPException(status_code=422, detail=str(refused)) from None
    except AutoSaveFull as full:
        raise HTTPException(status_code=409, detail=_refusal(full.slot)) from None

    for field, value in changes.items():
        setattr(packing_list, field, value)

    db.commit()
    db.refresh(packing_list)
    return packing_list
```

- [ ] **Step 5: Run**

Run: `venv/Scripts/python.exe -m pytest tests/api/test_packing_list_router.py tests/api/test_packing_item_router.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/schemas/packing_list.py app/routers/packing_list.py tests/api/test_packing_list_router.py \
  tests/api/test_trip_router.py tests/api/test_trip_copy.py
git commit -m "feat: the packing-list API speaks kind and usage, with four shelves"
```

---

### Task 4: Trip API, the current trip and bulk delete

**Files:**
- Modify: `app/schemas/trip.py`, `app/routers/trip.py`, `app/services/domain/trip.py`, `tests/api/test_trip_router.py`, `tests/api/test_trip_copy.py`

**Interfaces:**
- Consumes: Task 2's `auto_save` names.
- Produces: `GET /api/trips` → `{free, auto_saved, saved, templates, evict_next}` of `TripResponse` (legs nested); trip reads carry `kind`, `usage`, `auto_saved_at`, `notes`, `archive_note`; `POST /api/trips` takes `kind` (`free`|`template`); `PATCH` takes `kind` (`saved`|`free`), `usage`, `notes`, `archive_note`, `evict_confirmed`; `POST /api/trips/bulk-delete {ids}` → `204`; `current_trip(db, now)` by usage.

- [ ] **Step 1: Rewrite the trip tests.** In `tests/api/test_trip_router.py` delete every test from `test_there_is_no_current_trip_without_legs` to `test_archiving_the_current_trip_moves_the_current_endpoint`, `test_trips_list_newest_latest_departure_first_and_legless_last`, and every test from `test_a_new_trip_is_neither_archived_nor_a_template` to the end of the archive/template block. Add:

```python
from app.constants import Kind, Usage

NOW = datetime(2026, 9, 25, tzinfo=timezone.utc)


def a_trip(db_session, name, usage=Usage.UNUSED, legs=(), **fields):
    trip = Trip(name=name, usage=usage, **fields)
    for days in legs:
        departs = NOW + timedelta(days=days)
        trip.legs.append(TripLeg(from_place="a", to_place="b", departs_at=departs,
                                 arrives_at=departs + timedelta(hours=1)))
    db_session.add(trip)
    db_session.flush()
    return trip


def test_in_use_beats_upcoming(db_session):
    a_trip(db_session, "upcoming", Usage.UPCOMING, legs=[1])
    in_use = a_trip(db_session, "in use", Usage.IN_USE, legs=[30])
    assert current_trip(db_session, NOW).id == in_use.id


def test_upcoming_when_nothing_is_in_use(db_session):
    a_trip(db_session, "unused", Usage.UNUSED, legs=[1])
    upcoming = a_trip(db_session, "upcoming", Usage.UPCOMING, legs=[30])
    assert current_trip(db_session, NOW).id == upcoming.id


def test_within_a_group_the_soonest_leg_ahead_wins(db_session):
    a_trip(db_session, "later", Usage.IN_USE, legs=[10])
    sooner = a_trip(db_session, "sooner", Usage.IN_USE, legs=[-5, 2])
    assert current_trip(db_session, NOW).id == sooner.id


def test_a_trip_with_nothing_ahead_comes_after_one_with_a_leg_ahead(db_session):
    a_trip(db_session, "done", Usage.IN_USE, legs=[-3])
    ahead = a_trip(db_session, "ahead", Usage.IN_USE, legs=[40])
    assert current_trip(db_session, NOW).id == ahead.id


def test_a_legless_in_use_trip_is_current_and_ties_go_to_the_newer(db_session):
    a_trip(db_session, "first", Usage.IN_USE)
    second = a_trip(db_session, "second", Usage.IN_USE)
    assert current_trip(db_session, NOW).id == second.id


@pytest.mark.parametrize("fields", [
    {"usage": Usage.UNUSED}, {"usage": Usage.PAST, "auto_saved_at": NOW},
    {"kind": Kind.SAVED, "usage": None}, {"kind": Kind.TEMPLATE, "usage": None},
])
def test_only_in_use_or_upcoming_trips_can_be_current(db_session, fields):
    a_trip(db_session, "other", legs=[1], **fields)
    assert current_trip(db_session, NOW) is None
    upcoming = a_trip(db_session, "mirror", Usage.UPCOMING, legs=[1])  # same rows, one eligible
    assert current_trip(db_session, NOW).id == upcoming.id


def test_the_current_endpoint_is_404_when_there_is_none(client):
    response = client.get("/api/trips/current")
    assert response.status_code == 404
    assert response.json()["detail"] == "No current trip."


def test_the_current_endpoint_follows_usage(client, trip):
    assert client.get("/api/trips/current").status_code == 404
    client.patch(f"/api/trips/{trip['id']}", json={"usage": "in_use"})
    assert client.get("/api/trips/current").json()["id"] == trip["id"]


def test_the_index_has_four_shelves(client, db_session):
    a_trip(db_session, "free")
    a_trip(db_session, "auto", Usage.PAST, auto_saved_at=NOW)
    a_trip(db_session, "kept", None, kind=Kind.SAVED)
    a_trip(db_session, "tpl", None, kind=Kind.TEMPLATE)
    db_session.commit()
    body = client.get("/api/trips").json()
    assert {name: [t["name"] for t in body[name]] for name in ("free", "auto_saved", "saved", "templates")} \
        == {"free": ["free"], "auto_saved": ["auto"], "saved": ["kept"], "templates": ["tpl"]}
    assert body["evict_next"] == []


def test_the_free_shelf_is_newest_latest_departure_first_and_legless_last(client, db_session):
    a_trip(db_session, "legless")
    a_trip(db_session, "early", legs=[1])
    a_trip(db_session, "late", legs=[9])
    db_session.commit()
    assert [t["name"] for t in client.get("/api/trips").json()["free"]] == ["late", "early", "legless"]


@pytest.fixture
def ten_auto_saved(db_session):
    """The trip queue at its limit. Load-bearing."""
    rows = [a_trip(db_session, f"T{d}", Usage.PAST, auto_saved_at=NOW + timedelta(days=d)) for d in range(10)]
    db_session.commit()
    return rows


def test_past_when_ten_are_auto_saved_is_a_409(ten_auto_saved, client, trip):
    refused = client.patch(f"/api/trips/{trip['id']}", json={"usage": "past"})
    assert refused.status_code == 409
    assert "T0" in refused.json()["detail"]
    assert client.get("/api/trips").json()["evict_next"][0]["name"] == "T0"


def test_past_confirmed_drops_the_oldest_trip(ten_auto_saved, client, db_session, trip):
    oldest = ten_auto_saved[0].id
    body = client.patch(f"/api/trips/{trip['id']}", json={"usage": "past", "evict_confirmed": True}).json()
    assert body["usage"] == "past"
    db_session.expire_all()
    assert db_session.get(Trip, oldest) is None


def test_past_with_room_is_not_refused(ten_auto_saved, client, db_session, trip):
    db_session.delete(ten_auto_saved[-1])
    db_session.commit()
    assert client.patch(f"/api/trips/{trip['id']}", json={"usage": "past"}).status_code == 200


def test_saving_a_trip_keeps_its_archive_note(client, trip):
    url = f"/api/trips/{trip['id']}"
    body = client.patch(url, json={"kind": "saved", "archive_note": "下次早點訂票"}).json()
    assert (body["kind"], body["usage"], body["archive_note"]) == ("saved", None, "下次早點訂票")
    body = client.patch(url, json={"kind": "free"}).json()
    assert (body["kind"], body["usage"], body["archive_note"]) == ("free", "unused", "下次早點訂票")


@pytest.mark.parametrize("payload", [{"kind": "template"}, {"kind": None}, {"usage": None}])
def test_a_trip_refuses_impossible_moves(client, trip, payload):
    assert client.patch(f"/api/trips/{trip['id']}", json=payload).status_code == 422


def test_a_trip_template_can_be_created(client):
    body = client.post("/api/trips", json={"name": "x", "kind": "template"}).json()
    assert (body["kind"], body["usage"]) == ("template", None)


def test_bulk_delete_deletes_every_named_trip(client, db_session):
    rows = [a_trip(db_session, f"t{i}") for i in range(3)]
    db_session.commit()
    ids = [rows[0].id, rows[1].id, rows[1].id]  # a duplicate is deleted once
    assert client.post("/api/trips/bulk-delete", json={"ids": ids}).status_code == 204
    db_session.expire_all()
    assert [db_session.get(Trip, row.id) is None for row in rows] == [True, True, False]


def test_bulk_delete_with_a_missing_id_deletes_nothing(client, db_session):
    row = a_trip(db_session, "t")
    db_session.commit()
    response = client.post("/api/trips/bulk-delete", json={"ids": [row.id, 999999]})
    assert response.status_code == 404
    db_session.expire_all()
    assert db_session.get(Trip, row.id) is not None


def test_bulk_delete_of_nothing_is_a_204(client):
    assert client.post("/api/trips/bulk-delete", json={"ids": []}).status_code == 204
```

In `tests/api/test_trip_copy.py`: the source fixture's `json={"template": True, "archived": True, "archive_note": "舊的"}` becomes `json={"kind": "saved", "archive_note": "舊的"}`, and `assert (new["archived"], new["archive_note"], new["template"]) == (False, None, False)` becomes `assert (new["kind"], new["usage"], new["archive_note"]) == ("free", "unused", None)`. Add:

```python
def test_copying_as_a_template_keeps_the_dates_when_given_the_first_day(client):
    source = client.post("/api/trips", json={"name": "s"}).json()
    client.post(f"/api/trips/{source['id']}/legs", json={
        "from_place": "a", "to_place": "b",
        "departs_at": "2026-09-24T18:06:00+08:00", "arrives_at": "2026-09-24T20:59:00+08:00"})
    copy = client.post("/api/trips", json={"name": "s（範本）", "kind": "template",
                                           "copy_from_id": source["id"], "start_date": "2026-09-24"}).json()
    assert copy["kind"] == "template"
    assert copy["legs"][0]["departs_at"].startswith("2026-09-24T10:06:00")
```

- [ ] **Step 2: Run to verify failure**

Run: `venv/Scripts/python.exe -m pytest tests/api/test_trip_router.py tests/api/test_trip_copy.py -q`
Expected: FAIL.

- [ ] **Step 3: Schemas** — in `app/schemas/trip.py` replace `TripUpdate`, `TripResponse`, `TripCreate` and add the index and bulk body:

```python
class TripUpdate(NonNullableUpdate):
    non_nullable = ("name", "kind", "usage")

    name: str | None = Field(default=None, min_length=1)
    notes: str | None = None
    archive_note: str | None = None
    #: 保存 or 取消保存. A template is made by creating one.
    kind: Literal["saved", "free"] | None = None
    usage: Usage | None = None
    #: Acknowledges that 過去使用 may drop the oldest 自動保存 trip.
    evict_confirmed: bool = False


class TripResponse(TripBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: Kind
    usage: Usage | None
    auto_saved_at: datetime | None
    archive_note: str | None = None
    legs: list[TripLegResponse] = []


class TripCreate(TripBase):
    """`kind` is 一般 or 範本. `copy_from_id` copies another trip; `start_date`
    is the Taipei day its first leg moves to, required when that trip has legs."""

    kind: Literal["free", "template"] = "free"
    copy_from_id: int | None = None
    start_date: date | None = None


class TripIndex(BaseModel):
    """The same four shelves as packing lists, plus what 過去使用 would drop."""

    free: list[TripResponse]
    auto_saved: list[TripResponse]
    saved: list[TripResponse]
    templates: list[TripResponse]
    evict_next: list[TripResponse]


class TripIds(BaseModel):
    ids: list[int]
```

Imports: `from datetime import date, datetime`; `from typing import Literal`; `from app.constants import Kind, Usage`. `TripCreated(TripResponse)` is unchanged.

- [ ] **Step 4: The current trip** — replace `current_trip` in `app/services/domain/trip.py`:

```python
def current_trip(db: Session, now: datetime) -> Trip | None:
    """The 使用中 trip; with none, the 未來使用 one. Within a group, the trip
    whose soonest leg still ahead is earliest; trips with nothing ahead come
    after, newest (highest id) first. A trip with no legs can be current - its
    status, not its legs, says it is the one being taken.
    """
    trips = (
        db.execute(
            select(Trip)
            .where(Trip.kind == Kind.FREE, Trip.usage.in_([Usage.IN_USE, Usage.UPCOMING]))
            .options(selectinload(Trip.legs))
        )
        .scalars()
        .all()
    )

    def rank(trip: Trip):
        ahead = [leg.departs_at for leg in trip.legs if leg.departs_at > now]
        return (0, min(ahead).timestamp(), -trip.id) if ahead else (1, 0, -trip.id)

    for usage in (Usage.IN_USE, Usage.UPCOMING):
        group = [trip for trip in trips if trip.usage == usage]
        if group:
            return min(group, key=rank)
    return None
```

Import `Kind, Usage` from `app.constants`. Module docstring: `"""Which trip is current, and what a copied trip carries."""`.

- [ ] **Step 5: Router** — in `app/routers/trip.py`: import `TripIds, TripIndex` and `from app.services.domain.auto_save import AutoSaveFull, KindRefused, apply_kind, evict_next` and `from app.constants import Kind, LabelKind, Usage`. Replace `list_trips`:

```python
def _refusal(slot: list[Trip]) -> str:
    names = " and ".join(f'"{trip.name}"' for trip in slot)
    return (
        f"Auto-save already holds 10 trips. Marking this one past would delete "
        f"{names}, the oldest. Save it first if you want to keep it, or confirm "
        f"to replace it."
    )


@router.get("/api/trips", response_model=TripIndex)
def list_trips(db: Session = Depends(get_db)):
    trips = db.scalars(_trips_query()).all()
    # Newest first by latest departure; a trip with no legs goes last.
    ordered = sorted(
        trips,
        key=lambda trip: (
            bool(trip.legs),
            max((leg.departs_at for leg in trip.legs), default=_EARLIEST),
            trip.id,
        ),
        reverse=True,
    )
    auto_saved = sorted(
        (t for t in trips if t.kind == Kind.FREE and t.usage == Usage.PAST),
        key=lambda trip: (trip.auto_saved_at, trip.id),
        reverse=True,
    )
    return TripIndex(
        free=[t for t in ordered if t.kind == Kind.FREE and t.usage != Usage.PAST],
        auto_saved=auto_saved,
        saved=[t for t in ordered if t.kind == Kind.SAVED],
        templates=[t for t in ordered if t.kind == Kind.TEMPLATE],
        evict_next=evict_next(db, Trip),
    )


@router.post("/api/trips/bulk-delete", status_code=204)
def bulk_delete_trips(payload: TripIds, db: Session = Depends(get_db)):
    """All or nothing: one missing id refuses the whole request."""
    ids = set(payload.ids)
    trips = db.scalars(select(Trip).where(Trip.id.in_(ids))).all() if ids else []
    if len(trips) != len(ids):
        raise HTTPException(status_code=404, detail=TRIP_NOT_FOUND)
    for trip in trips:
        db.delete(trip)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

In `create_trip` change the dump to `Trip(**payload.model_dump(exclude={"copy_from_id", "start_date"}))` (unchanged text; `kind` now flows through). Replace `update_trip`'s body:

```python
    trip = _get_trip(db, trip_id)
    changes = payload.model_dump(exclude_unset=True, exclude={"evict_confirmed"})
    try:
        apply_kind(db, trip, changes, confirmed=payload.evict_confirmed, now=datetime.now(timezone.utc))
    except KindRefused as refused:
        raise HTTPException(status_code=422, detail=str(refused)) from None
    except AutoSaveFull as full:
        raise HTTPException(status_code=409, detail=_refusal(full.slot)) from None
    for field, value in changes.items():
        setattr(trip, field, value)
    db.commit()
    db.expire_all()
    return _get_trip(db, trip_id)
```

- [ ] **Step 6: Run the whole backend suite (take the lock)**

Run: `venv/Scripts/python.exe -m pytest tests/ -q` then `venv/Scripts/ruff.exe check .`
Expected: all pass (the three `python3` failures in the *platform* repo do not apply here); ruff clean. Fix `tests/api/test_sheet_import.py` if it asserts `saved` — it should assert `kind == "saved"`.

- [ ] **Step 7: Commit**

```bash
git add app/schemas/trip.py app/routers/trip.py app/services/domain/trip.py \
  tests/api/test_trip_router.py tests/api/test_trip_copy.py tests/api/test_sheet_import.py
git commit -m "feat: trips speak kind and usage; the current trip follows usage; bulk delete"
```

---

### Task 5: Frontend vocabulary and helpers

**Files:**
- Modify: `frontend/src/lib/labels.js`, `frontend/src/lib/labels.test.js`, `frontend/src/lib/trips.js`, `frontend/src/lib/trips.test.js`, `frontend/src/api/endpoints.js`, `frontend/src/components/EvictDialog.jsx`
- Create: `frontend/src/lib/kinds.js`, `frontend/src/lib/kinds.test.js`, `frontend/src/components/KindControls.jsx`

**Interfaces:**
- Produces:
  - `labels.js`: `KIND_LABELS = { template: '範本', saved: '保存', free: '一般' }`, `AUTO_SAVED_LABEL = '自動保存'`, `USAGES = ['in_use', 'upcoming', 'unused', 'past']`, `USAGE_LABELS = { in_use: '使用中', upcoming: '未來使用', unused: '未使用', past: '過去使用' }`
  - `kinds.js`: `AUTO_SAVE_LIMIT = { lists: 5, trips: 10 }`; `isAutoSaved(row)`; `badgeFor(row)` → `'範本' | '保存' | '自動保存' | null`; `onDashboard(rows)` → free rows with usage `in_use`/`upcoming`, `in_use` first, order otherwise kept; `everyRow(index)` → `[...free, ...auto_saved, ...saved, ...templates]` without duplicates; `templateName(name)` → `` `${name}（範本）` ``; `leavesCurrent(changes)` → true when `changes` sets `kind: 'saved'` or a `usage` other than `in_use`/`upcoming`.
  - `endpoints.trips.bulkDelete()` → `'/api/trips/bulk-delete'`
  - `EvictDialog` props unchanged; default `body` and `confirmLabel` become generic (below).
  - `KindControls({ row, onPatch, onMakeTemplate, compact })` — renders the 狀態 select (free rows only), the 保存 checkbox (non-template rows), the 當作範本 button; handles the 取消保存 confirmation itself; `onPatch(changes)` receives `{usage}` or `{kind}`.

- [ ] **Step 1: Failing tests** — `frontend/src/lib/kinds.test.js`:

```js
import { describe, expect, it } from 'vitest'

import { badgeFor, everyRow, isAutoSaved, leavesCurrent, onDashboard, templateName } from './kinds'

const row = (id, kind = 'free', usage = kind === 'free' ? 'unused' : null) => ({ id, kind, usage })

describe('isAutoSaved and badgeFor', () => {
  it('reads auto-saved from free + past only', () => {
    expect(isAutoSaved(row(1, 'free', 'past'))).toBe(true)
    expect(isAutoSaved(row(2, 'free', 'in_use'))).toBe(false)
    expect(isAutoSaved(row(3, 'saved'))).toBe(false)
  })
  it('names every kind but plain free', () => {
    expect([row(1, 'template'), row(2, 'saved'), row(3, 'free', 'past'), row(4)].map(badgeFor))
      .toEqual(['範本', '保存', '自動保存', null])
  })
})

describe('onDashboard', () => {
  it('keeps in-use and upcoming free rows, in-use first, order otherwise kept', () => {
    const rows = [row(1, 'free', 'upcoming'), row(2, 'free', 'unused'), row(3, 'free', 'in_use'),
      row(4, 'free', 'past'), row(5, 'saved'), row(6, 'free', 'upcoming'), row(7, 'free', 'in_use')]
    expect(onDashboard(rows).map((r) => r.id)).toEqual([3, 7, 1, 6])
  })
})

describe('everyRow', () => {
  it('concatenates the four shelves once each', () => {
    const index = { free: [row(1)], auto_saved: [row(2)], saved: [row(3)], templates: [row(4)] }
    expect(everyRow(index).map((r) => r.id)).toEqual([1, 2, 3, 4])
  })
})

describe('templateName and leavesCurrent', () => {
  it('suffixes 範本', () => expect(templateName('札幌')).toBe('札幌（範本）'))
  it('is true for saving or a usage that is not current', () => {
    expect(leavesCurrent({ kind: 'saved' })).toBe(true)
    expect(leavesCurrent({ usage: 'past' })).toBe(true)
    expect(leavesCurrent({ usage: 'unused' })).toBe(true)
    expect(leavesCurrent({ usage: 'upcoming' })).toBe(false)
    expect(leavesCurrent({ usage: 'in_use' })).toBe(false)
    expect(leavesCurrent({ name: 'x' })).toBe(false)
  })
})
```

Add to `labels.test.js` (match its existing walk style):

```js
import { KIND_LABELS, USAGES, USAGE_LABELS } from './labels'

it('labels every kind and usage', () => {
  for (const kind of ['template', 'saved', 'free']) expect(KIND_LABELS[kind]).toBeTruthy()
  for (const usage of USAGES) expect(USAGE_LABELS[usage]).toBeTruthy()
})
```

- [ ] **Step 2: Run** `cd frontend && npx vitest run src/lib/kinds.test.js src/lib/labels.test.js` — Expected: FAIL (module not found).

- [ ] **Step 3: Implement.** Append to `labels.js`:

```js
/** Which shelf a list or trip is on. 自動保存 is free + past, not a stored kind. */
export const KIND_LABELS = { template: '範本', saved: '保存', free: '一般' }
export const AUTO_SAVED_LABEL = '自動保存'

export const USAGES = ['in_use', 'upcoming', 'unused', 'past']
export const USAGE_LABELS = {
  in_use: '使用中',
  upcoming: '未來使用',
  unused: '未使用',
  past: '過去使用',
}
```

Create `kinds.js`:

```js
/**
 * Kinds and usage, shared by packing lists and trips. Pure, so the shelf
 * rules the screens rely on are tested once.
 */

import { AUTO_SAVED_LABEL, KIND_LABELS } from './labels'

export const AUTO_SAVE_LIMIT = { lists: 5, trips: 10 }

const CURRENT = ['in_use', 'upcoming']

export const isAutoSaved = (row) => row.kind === 'free' && row.usage === 'past'

/** The badge beside a name: every kind but a plain 一般 one. */
export function badgeFor(row) {
  if (isAutoSaved(row)) return AUTO_SAVED_LABEL
  return row.kind === 'free' ? null : KIND_LABELS[row.kind]
}

/** 一般 rows that are 使用中 or 未來使用, 使用中 first, order otherwise kept. */
export function onDashboard(rows) {
  const current = rows.filter((row) => row.kind === 'free' && CURRENT.includes(row.usage))
  return [
    ...current.filter((row) => row.usage === 'in_use'),
    ...current.filter((row) => row.usage === 'upcoming'),
  ]
}

/** Every row of an index response, each once. */
export function everyRow(index) {
  const seen = new Set()
  return [...index.free, ...index.auto_saved, ...index.saved, ...index.templates].filter((row) =>
    seen.has(row.id) ? false : seen.add(row.id),
  )
}

export const templateName = (name) => `${name}（範本）`

/** Whether a PATCH takes the trip on /trip out of being current. */
export const leavesCurrent = (changes) =>
  changes.kind === 'saved' || ('usage' in changes && !CURRENT.includes(changes.usage))
```

Leave `lib/trips.js` alone here: Task 7 deletes `partitionTrips`, `templateChoices` and `archivePatch` (and their tests) when `Trip.jsx` stops using them, and Task 8 deletes `dashboardTrips`. Deleting them now would break the build between commits.

`endpoints.js` → in `trips` add `bulkDelete: () => '/api/trips/bulk-delete',`.

`EvictDialog.jsx`: change the docstring's first line to `* What stands between 過去使用 and a dropped list or trip.`, delete `CREATE_BODY`, and make the defaults `body` (required, no default) and `confirmLabel = '刪除並繼續'`; the title becomes `這會刪除{noun}` with a new prop `noun = '一份清單'`.

Create `components/KindControls.jsx`:

```jsx
/**
 * 狀態, 保存 and 當作範本 for one list or trip, wherever it is shown.
 *
 * 取消保存 asks first, because it puts the row back among the 一般 ones as
 * 未使用 - the dialog lives here so every place that shows the checkbox asks
 * the same question.
 */

import { useState } from 'react'

import { USAGES, USAGE_LABELS } from '../lib/labels'
import { ConfirmDialog } from './ConfirmDialog'

export function KindControls({ row, noun, onPatch, onMakeTemplate }) {
  const [confirmingUnsave, setConfirmingUnsave] = useState(false)
  if (row.kind === 'template') return null
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      {row.kind === 'free' && (
        <select
          aria-label={`「${row.name}」的狀態`}
          value={row.usage}
          onChange={(event) => onPatch({ usage: event.target.value })}
          className="rounded-md border border-border bg-canvas px-2 py-1 text-sm text-text"
        >
          {USAGES.map((usage) => (
            <option key={usage} value={usage}>
              {USAGE_LABELS[usage]}
            </option>
          ))}
        </select>
      )}
      <label className="flex items-center gap-1 text-text-muted">
        <input
          type="checkbox"
          checked={row.kind === 'saved'}
          onChange={(event) =>
            event.target.checked ? onPatch({ kind: 'saved' }) : setConfirmingUnsave(true)
          }
          className="size-4"
        />
        保存
      </label>
      <button
        type="button"
        onClick={onMakeTemplate}
        className="rounded-md border border-border-strong px-3 text-sm text-text-muted"
        style={{ minHeight: 32 }}
      >
        當作範本
      </button>
      {confirmingUnsave && (
        <ConfirmDialog
          title={`取消保存「${row.name}」？`}
          body={`取消保存後會回到一般${noun}（未使用）。`}
          confirmLabel="取消保存"
          onConfirm={() => {
            setConfirmingUnsave(false)
            onPatch({ kind: 'free' })
          }}
          onCancel={() => setConfirmingUnsave(false)}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run** `npx vitest run` — Expected: PASS.

- [ ] **Step 5: Commit** together with Task 6, so the new components land with their first consumer. Proceed to Task 6.

---

### Task 6: `/lists` and the list page

**Files:**
- Modify: `frontend/src/pages/PackingLists.jsx`, `frontend/src/pages/PackingList.jsx`

**Interfaces:**
- Consumes: Task 5's helpers, `KindControls`, `EvictDialog`; API from Task 3.

- [ ] **Step 1: `PackingLists.jsx`.** Replace the module docstring with:

```js
/**
 * Every list, on four shelves: 一般, 自動保存（n / 5）, 保存 and 範本.
 *
 * Sections rather than tabs, because there are rarely more than a handful.
 * Each row carries its own 狀態, 保存 and 當作範本; 過去使用 into a full
 * 自動保存 is the one change that asks first, naming the list it would drop.
 */
```

Replace `Table`'s header and row with columns 清單 · 出發 · 已處理 · (controls), where the controls cell renders
`<KindControls row={row} noun="清單" onPatch={(changes) => onPatch(row, changes)} onMakeTemplate={() => onMakeTemplate(row)} />`, and under the name, for saved and auto-saved rows, `{row.archive_note && <span className="block text-xs text-text-faint">{firstLine(row.archive_note)}</span>}` (import `firstLine` from `../lib/trips`). Rename the `onFlag` prop to `onPatch`.

Replace the page body's state and mutations:

```jsx
  const [draft, setDraft] = useState({ name: '', departure_at: '', copy_from_id: '', kind: 'free' })
  const [refusal, setRefusal] = useState(null) // { id, changes } of a refused 過去使用
  const [madeTemplate, setMadeTemplate] = useState(null)

  const create = useApiMutation({
    invalidate: [INDEX_KEY],
    mutationFn: (payload) => send(endpoints.packingLists.index(), 'POST', payload),
    onSuccess: () => {
      setDraft({ name: '', departure_at: '', copy_from_id: '', kind: 'free' })
      setOpen(false)
    },
  })
  const makeTemplate = useApiMutation({
    invalidate: [INDEX_KEY],
    mutationFn: (row) =>
      send(endpoints.packingLists.index(), 'POST', {
        name: templateName(row.name), kind: 'template', copy_from_id: row.id,
      }),
    onSuccess: (created) => setMadeTemplate(created),
  })
  const patch = useApiMutation({
    invalidate: [INDEX_KEY],
    mutationFn: ({ id, changes }) => send(endpoints.packingLists.detail(id), 'PATCH', changes),
    onError: (error, variables) => {
      // A 409 is a decision to put to the person, not a failure to report.
      if (error.status === 409) setRefusal(variables)
    },
  })
```

and after the loading/error guards:

```jsx
  const index = indexQuery.data
  const copyable = everyRow(index)
  const onPatch = (row, changes) => patch.mutate({ id: row.id, changes })
```

(rename the query constant to `indexQuery`). The form gains, before 從哪份清單複製項目:

```jsx
            <label className="text-xs text-text-faint">
              類型
              <select
                value={draft.kind}
                onChange={(event) => setDraft({ ...draft, kind: event.target.value })}
                className="mt-1 block rounded-md border border-border bg-canvas px-3 py-2 text-base text-text"
              >
                <option value="free">{KIND_LABELS.free}</option>
                <option value="template">{KIND_LABELS.template}</option>
              </select>
            </label>
```

and `payload()` adds `kind: draft.kind`. The copy select's option suffix becomes `{badgeFor(row) ? `（${badgeFor(row)}）` : ''}`.

The sections:

```jsx
      {madeTemplate && (
        <p className="mx-4 mt-4 rounded-md bg-surface-2 px-3 py-2 text-sm">
          已建立範本 <Link to={`/lists/${madeTemplate.id}`}>{madeTemplate.name}</Link>。
          <button type="button" onClick={() => setMadeTemplate(null)} className="ml-2 text-text-muted">
            知道了
          </button>
        </p>
      )}
      <Table title={KIND_LABELS.free} rows={index.free}
        empty="目前沒有一般清單。從上面新增一份。" onPatch={onPatch} onMakeTemplate={makeTemplate.mutate} />
      <Table title={AUTO_SAVED_LABEL} count={`${index.auto_saved.length} / ${AUTO_SAVE_LIMIT.lists}`}
        rows={index.auto_saved} empty="把一般清單的狀態設為「過去使用」，它會自動保存在這裡。"
        onPatch={onPatch} onMakeTemplate={makeTemplate.mutate} />
      <Table title={KIND_LABELS.saved} rows={index.saved}
        empty="在清單上勾選「保存」，它就不會被自動刪除。" onPatch={onPatch} onMakeTemplate={makeTemplate.mutate} />
      <Table title={KIND_LABELS.template} rows={index.templates}
        empty="按「當作範本」或新增一份範本，之後的新清單可以從它開始。"
        onPatch={onPatch} onMakeTemplate={makeTemplate.mutate} />

      {refusal && (
        <EvictDialog
          noun="一份清單"
          body={`自動保存最多 ${AUTO_SAVE_LIMIT.lists} 份清單。設為過去使用會刪除最舊的：`}
          evicting={index.evict_next}
          onSaveInstead={async () => {
            await Promise.all(index.evict_next.map((row) =>
              patch.mutateAsync({ id: row.id, changes: { kind: 'saved' } })))
            setRefusal(null)
            patch.mutate(refusal)
          }}
          onConfirm={() => {
            setRefusal(null)
            patch.mutate({ ...refusal, changes: { ...refusal.changes, evict_confirmed: true } })
          }}
          onCancel={() => setRefusal(null)}
        />
      )}
```

Imports: `KindControls`, `everyRow`, `badgeFor`, `templateName`, `AUTO_SAVE_LIMIT` from `../lib/kinds`; `KIND_LABELS`, `AUTO_SAVED_LABEL` from `../lib/labels`. Remove the old 409-on-create path and its dialog — creating is never refused now.

- [ ] **Step 2: `PackingList.jsx` header.** Below `<Departure .../>` add:

```jsx
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {badgeFor(list.data) && <span className={badge}>{badgeFor(list.data)}</span>}
          <KindControls
            row={list.data}
            noun="清單"
            onPatch={(changes) => patchList.mutate(changes)}
            onMakeTemplate={() => makeTemplate.mutate()}
          />
        </div>
        <TextCell value={list.data.notes} placeholder="備註" onCommit={(notes) => patchList.mutate({ notes })} />
        {(list.data.kind === 'saved' || isAutoSaved(list.data) || list.data.archive_note) && (
          <TextCell
            value={list.data.archive_note}
            placeholder="保存備註"
            onCommit={(archive_note) => patchList.mutate({ archive_note })}
          />
        )}
```

with `const badge = 'shrink-0 rounded-sm bg-surface-2 px-2 text-xs text-text-muted'` at module level, and:

```jsx
  const [refusal, setRefusal] = useState(null)
  const patchList = useApiMutation({
    invalidate: [key, ['packing-lists']],
    mutationFn: (changes) => send(endpoints.packingLists.detail(listId), 'PATCH', changes),
    onError: (error, changes) => {
      if (error.status === 409) setRefusal(changes)
    },
  })
  const lists = useApiQuery(['packing-lists'], endpoints.packingLists.index(), { enabled: Boolean(refusal) })
  const makeTemplate = useApiMutation({
    invalidate: [['packing-lists']],
    mutationFn: () =>
      send(endpoints.packingLists.index(), 'POST', {
        name: templateName(list.data.name), kind: 'template', copy_from_id: list.data.id,
      }),
    onSuccess: (created) => navigate(`/lists/${created.id}`),
  })
```

(replacing the existing `patchList`), and an `EvictDialog` exactly as in Step 1 but with `evicting={lists.data?.evict_next ?? []}`, `onSaveInstead` saving those then `patchList.mutate(refusal)`, and `onConfirm` → `patchList.mutate({ ...refusal, evict_confirmed: true })`.

- [ ] **Step 3: Verify** — `cd frontend && npm test && npm run lint && npm run build`. Expected: green. Then start `.\dev.ps1` (or reuse a running one), open `http://127.0.0.1:5175/lists`, and check: create a 範本 from blank; 當作範本 on a 一般 list makes `…（範本）`; set a list 過去使用 and see it move to 自動保存; untick 保存 and see the confirmation. Report what was checked.

- [ ] **Step 4: Commit (Tasks 5 + 6)**

```bash
git add frontend/src/lib/labels.js frontend/src/lib/labels.test.js frontend/src/lib/kinds.js \
  frontend/src/lib/kinds.test.js frontend/src/lib/trips.js frontend/src/lib/trips.test.js \
  frontend/src/api/endpoints.js frontend/src/components/EvictDialog.jsx \
  frontend/src/components/KindControls.jsx frontend/src/pages/PackingLists.jsx frontend/src/pages/PackingList.jsx
git commit -m "feat: lists show four shelves with 狀態, 保存 and 當作範本"
```

`git add` above lists `lib/trips.js` and `lib/trips.test.js` only if Task 6 touched them; otherwise drop those two paths. Between Task 4 and Task 8 the trip screens run against the new API shape and are broken at runtime on this branch; the build stays green.

---

### Task 7: The 行程 page and 自動保存的行程

**Files:**
- Modify: `frontend/src/pages/Trip.jsx`, `frontend/src/App.jsx`
- Create: `frontend/src/pages/AutoSavedTrips.jsx`

**Interfaces:**
- Consumes: `KindControls`, `badgeFor`, `isAutoSaved`, `leavesCurrent`, `templateName`, `everyRow`, `AUTO_SAVE_LIMIT`; `GET /api/trips` object shape; bulk delete.

- [ ] **Step 1: `Trip.jsx`.**
  - Docstring: replace the archive sentence with `A trip carries 狀態, 保存 and 當作範本; the trips below it are split into 一般, 保存 and 範本, with a link to 自動保存的行程.`
  - Delete `TripMenu`'s archive/template actions — its actions become `[{ label: trip.kind === 'saved' ? '取消保存' : '保存', onSelect: onToggleSaved }, { label: '當作範本', onSelect: onMakeTemplate }, { label: '刪除行程', danger: true, onSelect: onDelete }]`, and for a template only `[{ label: '刪除行程', danger: true, onSelect: onDelete }]`. Delete `ArchiveDialog` entirely.
  - `PackingListLink`'s choice building becomes `const choices = lists.data ? everyRow(lists.data) : []`.
  - `TripSections({ index, currentId, templates, onCreate })`: sections are 一般 (`index.free` minus `currentId`, holding `NewTrip` as now), 保存 (`index.saved`), 範本 (`index.templates`), each omitted when empty except 一般 with `onCreate`; then

```jsx
      <p className="mt-6 border-t border-border pt-4">
        <Link to="/trips/auto-saved" className="text-brand">
          自動保存的行程（{index.auto_saved.length} / {AUTO_SAVE_LIMIT.trips}）→
        </Link>
      </p>
```

  `TripLinks` drops its `note` prop and shows `{badgeFor(trip) && <span className={badge}>{USAGE_LABELS[trip.usage] ?? badgeFor(trip)}</span>}` — a 一般 trip shows its 狀態, any other its kind.
  - `CreateTrip` gains a 類型 select (一般 / 範本) beside the name, and the payload adds `kind`. `templates` stays `index.templates`.
  - `TripView` header: replace the two badges with `{badgeFor(trip) && <span className={badge}>{badgeFor(trip)}</span>}`; under the name row add `<KindControls row={trip} noun="行程" onPatch={(changes) => patchKind(changes)} onMakeTemplate={makeTemplate} />` — `KindControls` already renders the 保存 checkbox, so the ⋯ 保存 item is the same action reached from the menu. The 封存備註 cell becomes:

```jsx
      {(trip.kind === 'saved' || isAutoSaved(trip) || trip.archive_note) && (
        <TextCell value={trip.archive_note} placeholder="保存備註"
          onCommit={(archive_note) => patchTrip({ archive_note })} />
      )}
```

  - `patchKind(changes)`: `patchTrip(changes, leavesCurrent(changes) ? onLeavingCurrent : undefined)`, with the 409 opening the same `EvictDialog` as Task 6 (`noun="一個行程"`, body `自動保存最多 10 個行程。設為過去使用會刪除最舊的：`, `evicting={allTrips.evict_next}`), save-instead patching each `{kind: 'saved'}` then retrying, confirm retrying with `evict_confirmed: true`. `actions.patchTrip` must therefore accept an `onError`; change `useTripMutation` to `useApiMutation({ invalidate: INVALIDATE, mutationFn, onError })` where the trip patch passes `onError: (error, variables) => error.status === 409 && setRefusal(variables)` — lift `refusal` state into `Trip()` and pass it down.
  - `makeTemplate`: `actions.createTrip.mutate({ name: templateName(trip.name), kind: 'template', copy_from_id: trip.id, ...(trip.legs.length ? { start_date: taipeiInputValue(sortLegs(trip.legs)[0].departs_at).slice(0, 10) } : {}) })` — `openNewTrip` already navigates to the new trip with its unlinked notice.
  - In `Trip()`: `all.data` is now the index object. `templates` = `all.data?.templates ?? []`; pass `allTrips={all.data}`; the no-current-trip empty state renders `<TripSections index={all.data} currentId={null} ... />` once `all.data` is loaded.

- [ ] **Step 2: `AutoSavedTrips.jsx`** — create:

```jsx
/**
 * 自動保存的行程: every 一般 trip set to 過去使用, newest first.
 *
 * 刪除模式 is here because this is where old trips pile up: ticking several
 * and deleting them at once beats ⋯ → 刪除 on each. One confirmation names
 * every trip it will delete.
 */

import { useState } from 'react'
import { Link } from 'react-router-dom'

import { endpoints } from '../api/endpoints'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { send, useApiMutation, useApiQuery } from '../hooks/useApiQuery'
import { AUTO_SAVE_LIMIT } from '../lib/kinds'
import { firstLine, tripDateRange } from '../lib/trips'

const smallButton = 'rounded-md border border-border-strong px-3 text-sm text-text-muted'

export default function AutoSavedTrips() {
  const index = useApiQuery(['trips', 'index'], endpoints.trips.index())
  const [deleting, setDeleting] = useState(false)
  const [selected, setSelected] = useState(new Set())
  const [confirming, setConfirming] = useState(false)
  const remove = useApiMutation({
    invalidate: [['trips'], ['packing-lists'], ['packing-list']],
    mutationFn: (ids) => send(endpoints.trips.bulkDelete(), 'POST', { ids }),
    onSuccess: () => {
      setSelected(new Set())
      setDeleting(false)
    },
  })

  if (index.isLoading) return <LoadingState label="載入行程中…" />
  if (index.isError) return <ErrorState error={index.error} onRetry={index.refetch} />

  const trips = index.data.auto_saved
  const toggle = (id) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelected(next)
  }
  const chosen = trips.filter((trip) => selected.has(trip.id))

  return (
    <main className="mx-auto max-w-4xl px-4 pb-16 pt-6">
      <Link to="/trip" className="text-sm text-text-faint no-underline">← 行程</Link>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <h1 className="m-0 text-xl font-semibold">
          自動保存的行程
          <span className="ml-2 text-sm font-normal text-text-faint">
            {trips.length} / {AUTO_SAVE_LIMIT.trips}
          </span>
        </h1>
        {trips.length > 0 && (
          <button type="button" className={smallButton} onClick={() => {
            setDeleting(!deleting)
            setSelected(new Set())
          }}>
            {deleting ? '完成' : '刪除模式'}
          </button>
        )}
      </div>

      {trips.length === 0 ? (
        <EmptyState>把一般行程的狀態設為「過去使用」，它會自動保存在這裡。</EmptyState>
      ) : (
        <>
          {deleting && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <label className="flex items-center gap-1 text-sm text-text-muted">
                <input
                  type="checkbox"
                  className="size-4"
                  checked={chosen.length === trips.length}
                  onChange={(event) =>
                    setSelected(event.target.checked ? new Set(trips.map((t) => t.id)) : new Set())
                  }
                />
                全選
              </label>
              <button
                type="button"
                disabled={chosen.length === 0}
                onClick={() => setConfirming(true)}
                className="rounded-md border border-danger px-3 text-sm text-danger disabled:opacity-40"
              >
                刪除所選（{chosen.length}）
              </button>
            </div>
          )}
          <ul className="m-0 mt-3 list-none border-t border-border p-0">
            {trips.map((trip) => (
              <li key={trip.id} className="flex items-center gap-3 border-b border-border py-2">
                {deleting && (
                  <input
                    type="checkbox"
                    className="size-4"
                    aria-label={`選取「${trip.name}」`}
                    checked={selected.has(trip.id)}
                    onChange={() => toggle(trip.id)}
                  />
                )}
                <Link to={`/trips/${trip.id}`} className="flex min-w-0 flex-1 justify-between gap-3 text-brand">
                  <span className="min-w-0">
                    {trip.name}
                    {trip.archive_note && (
                      <span className="ml-2 text-sm text-text-faint">{firstLine(trip.archive_note)}</span>
                    )}
                  </span>
                  <span className="shrink-0 tabular-nums text-text-faint">
                    {tripDateRange(trip.legs) ?? '沒有行程段'}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}

      {confirming && (
        <ConfirmDialog
          title={`刪除 ${chosen.length} 個行程？`}
          body={`${chosen.map((trip) => `「${trip.name}」`).join('、')}和它們所有的行程段都會一起刪除，連結的打包清單不受影響。`}
          confirmLabel="刪除"
          onConfirm={() => {
            setConfirming(false)
            remove.mutate(chosen.map((trip) => trip.id))
          }}
          onCancel={() => setConfirming(false)}
        />
      )}
    </main>
  )
}
```

- [ ] **Step 3: Route** — in `App.jsx` import `AutoSavedTrips` and add `<Route path="/trips/auto-saved" element={<AutoSavedTrips />} />` **above** `/trips/:tripId`.

- [ ] **Step 4: Verify** — `npm test && npm run lint && npm run build`; in the dev server: set a trip 使用中 and see `/trip` show it; set it 過去使用 on `/trip` and see the page move to `/trips/{id}`; open 自動保存的行程, enter 刪除模式, select two, delete with one confirmation. Report what was checked.

- [ ] **Step 4b: Remove the dead helpers** — delete `partitionTrips`, `templateChoices` and `archivePatch` from `lib/trips.js` and their `describe` blocks and imports from `lib/trips.test.js`; `npm test` stays green.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Trip.jsx frontend/src/pages/AutoSavedTrips.jsx frontend/src/App.jsx   frontend/src/lib/trips.js frontend/src/lib/trips.test.js
git commit -m "feat: trips carry 狀態, 保存 and 當作範本; 自動保存的行程 with 刪除模式"
```

---

### Task 8: Dashboard

**Files:**
- Modify: `frontend/src/pages/Dashboard.jsx`

- [ ] **Step 1: Rewrite the data part.** Remove the `['trips', 'current']` query, `hasStatus`, `ApiError` and the 目前 badge. The sections become:

```jsx
      <Section title="清單" more={{ to: '/lists', label: '所有清單' }}>
        <Lists rows={onDashboard(lists.data.free)} />
      </Section>
      <Section title="行程" more={{ to: '/trip', label: '前往行程' }}>
        <Trips trips={onDashboard(trips.data.free)} />
      </Section>
```

Each row shows `<Badge>{USAGE_LABELS[row.usage]}</Badge>` after the name. A trip links to `/trips/${trip.id}`. Empty texts: 目前沒有使用中或未來使用的清單。 / 目前沒有使用中或未來使用的行程。 Docstring: `The front page: 一般 lists and trips that are 使用中 or 未來使用, 使用中 first. Nothing to add or edit.` Then delete `dashboardTrips` from `lib/trips.js` and its `describe` block and import from `lib/trips.test.js`.

- [ ] **Step 2: Verify** — `npm test && npm run lint && npm run build`; dashboard shows only 使用中/未來使用 rows.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Dashboard.jsx frontend/src/lib/trips.js frontend/src/lib/trips.test.js
git commit -m "feat: the dashboard shows lists and trips that are 使用中 or 未來使用"
```

---

### Task 9: Docs, and retiring the spec and plan

**Files:**
- Modify: `docs/business-rules.md`, `docs/api.md`, `docs/data-model.md`, `docs/frontend.md`, `docs/notes/decisions.md`, `docs/deployment-selfhost.md`, `docs/sheet-import.md` (if it says lists are saved), `CLAUDE.md` (Status paragraph only if it names the cap)
- Delete: `docs/superpowers/specs/2026-10-01-usage-status-design.md`, `docs/superpowers/plans/2026-10-01-usage-status.md`

- [ ] **Step 1: Grep the claims, not the files.** `grep -rn "three\|3 份\|cap\|SLOT\|saved\|template\|archived\|封存\|current trip\|evict" docs/ CLAUDE.md` and rewrite each hit present-tense:
  - `business-rules.md`: replace "The three-list cap" with "Kinds, usage and 自動保存" (the model table, the rules list and the slot rules from the spec, as built); replace "The current trip" and "Archiving a trip" with the usage rule; "Copying a list"'s own-fields sentence lists `kind, usage, notes, archive_note`.
  - `api.md`: the packing-list and trip tables, the index section (four shelves + `evict_next`), the create/refusal section rewritten for `PATCH usage: past`, `kind` on create, bulk delete.
  - `data-model.md`: both tables' columns and the four check constraints.
  - `frontend.md`: the `/lists`, list header, 行程 and dashboard sections; a new `## 自動保存的行程` section; routes list gains `/trips/auto-saved`; "The 409 is a decision" now about 過去使用.
  - `decisions.md`: a new entry "Kinds replace flags; 自動保存 is free + past" with why (impossible combinations unstorable; one queue rule for two tables; 封存 and 保存 were one idea under two words) and the rejected alternatives (keep booleans + status; table per kind); note the both-saved-and-template migration choice and that the current trip follows usage rather than dates.
  - `deployment-selfhost.md` revision table: `k1ind0000001` — downgrade loses usage statuses and list remarks; a list or trip that was both saved/archived and a template comes back a template only.
- [ ] **Step 2: Delete the spec and plan** — `git rm docs/superpowers/specs/2026-10-01-usage-status-design.md docs/superpowers/plans/2026-10-01-usage-status.md`.
- [ ] **Step 3: Full verification (take the lock)** — `venv/Scripts/python.exe -m pytest tests/ -q`, `venv/Scripts/ruff.exe check .`, `cd frontend && npm test && npm run lint && npm run build`, `venv/Scripts/alembic.exe heads` (one head, `k1ind0000001`). Upgrade the local `travel` database (`alembic upgrade head`) and smoke the app.
- [ ] **Step 4: Commit**

```bash
git add docs/business-rules.md docs/api.md docs/data-model.md docs/frontend.md \
  docs/notes/decisions.md docs/deployment-selfhost.md
git commit -m "docs: kinds, usage and auto-save; retire their spec and plan"
```
