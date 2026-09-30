# Sheet parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make travel hold everything the owner's four Google Sheet tabs hold — packing items with detail/need/location, transport routes with timetables, and trips with booked legs — in a Traditional Chinese UI that follows the sheet, then import the sheet's data.

**Architecture:** Three Alembic revisions extend the schema (packing item fields, transport, trips). Rules live in `app/services/domain/`, routers only wire HTTP. An importer package (`app/services/sheet_import/`) parses an `.xlsx` export into plain dataclasses and writes them in one transaction; `scripts/import_sheet.py` is its CLI. The React frontend gets a single labels module for every display string, pure `lib/` helpers with vitest coverage, and two new pages.

**Tech Stack:** FastAPI 0.115, SQLAlchemy 2.0, Alembic 1.14, PostgreSQL 17, pydantic 2, pytest; openpyxl and tzdata (new); React 19, TanStack Query 5, react-router 7, Tailwind 4, vitest 5.

**Spec:** `docs/superpowers/specs/2026-09-30-sheet-parity-design.md` — read it before starting any task. Where this plan and the spec disagree, stop and report rather than choosing.

## Global Constraints

- Work on branch `feat/sheet-parity` in `C:\Users\q601513\Documents\personal\cg1618\travel`. Never commit to `dev` or `main`.
- Commit messages: `<type>: <summary>` like the existing history. **No trailers at all** — no `Co-Authored-By`, no `Claude-Session`, nothing mentioning Claude or AI. Stage exact paths only, never a directory; commit with `git commit -m "..." -- <exact paths>`.
- **Every pytest run takes the machine-wide lock**, even a single test (they share PostgreSQL):
  ```bash
  LOCK=/c/Users/$USERNAME/AppData/Local/Temp/anime_site_pytest.lock
  until mkdir "$LOCK" 2>/dev/null; do sleep 10; done
  venv/Scripts/python.exe -m pytest <args>; rc=$?
  rmdir "$LOCK"; exit $rc
  ```
  Below, `PYTEST <args>` means exactly that block with `<args>` substituted.
- `ruff check .` must stay clean; `cd frontend && npm run lint && npm test` must stay green.
- Never open `.env` or any credential file.
- Every constraint gets an explicit name (`ck_`, `uq_`, `fk_`, `ix_` prefixes). Enumerated columns are text + `CheckConstraint(in_clause(...))`, never PG ENUM.
- Stored values are English enum text; **every string a user sees is Traditional Chinese**, except the sheet's own English words `Double Check`, `Transportation`, `This time`, and the app name `travel`. All display strings for enums live in `frontend/src/lib/labels.js` and nowhere else.
- API `detail` strings stay English (they are the API contract in `docs/api.md`); the frontend never renders a known refusal's `detail` verbatim — it renders its own zh-TW text.
- Docs change in the same commit as the behaviour they describe (`docs/api.md`, `docs/data-model.md`, `docs/business-rules.md`, `docs/frontend.md`, `docs/testing.md` as applicable). Present tense, describing what is true now.
- Test names are sentences describing behaviour (`test_a_reset_leaves_no_need_alone`).
- Refusal tests make their set non-empty and assert the mirror case with the same fixture.
- Asia/Taipei is the timezone for every leg time and every derived date. Use `zoneinfo.ZoneInfo("Asia/Taipei")`; `tzdata` is a runtime dependency because Windows has no system tz database.

## Review Focus

1. **A packing list linked to a leg whose departure is just after midnight Taipei** — the list's date must be the Taipei calendar day, not the UTC one. Pinned in Task 5 (`test_a_linked_list_takes_the_taipei_date_of_its_leg`).
2. **Re-running the importer on a database that already has its data** — must refuse before writing anything and name every clash, not half-import. Pinned in Task 6 (`test_an_import_refuses_when_any_target_exists_and_writes_nothing`).
3. **Deleting a packing list that a leg links to** — the leg must survive with its link cleared. Pinned in Task 5 (`test_deleting_a_linked_list_keeps_the_leg`).
4. **Adding a variant in the middle of a list, then sorting and unsorting the sheet** — positions must stay contiguous and the new row must come back directly under its parent. Pinned in Task 2 (`test_after_id_inserts_directly_after_and_shifts_later_items`) and Task 7 (`groupRuns` tests).
5. **A departure time typed twice for the same option and day type** — a 409 with a usable message, not a 500 from the unique constraint. Pinned in Task 4 (`test_a_duplicate_departure_is_a_409`).

---

## File map

| File | Responsibility | Task |
| --- | --- | --- |
| `app/constants.py` | + `Need`, `DayType`; `LabelKind` + `location`, `ticket_type` | 1, 4, 5 |
| `app/models/packing_item.py` | + `detail`, `need`, `location` | 1 |
| `app/services/domain/labels.py` (new) | label-option rules, moved out of `packing.py`, kind → column map | 1 |
| `app/services/domain/packing.py` | copy carries new fields; `insert_after`; `reset_list` | 1, 2 |
| `alembic/versions/p2acking0002_item_detail_need_location.py` | revision 1 | 1 |
| `app/routers/packing_item.py`, `app/schemas/packing_item.py` | new fields, `after_id` | 1, 2 |
| `app/routers/packing_list.py` | `POST /{id}/reset`; departure source | 2, 5 |
| `app/models/transport.py`, `app/schemas/transport.py`, `app/routers/transport.py` | transport | 4 |
| `alembic/versions/t1ransport01_transport.py` | revision 2 | 4 |
| `app/models/trip.py`, `app/schemas/trip.py`, `app/routers/trip.py`, `app/services/domain/trip.py` | trips | 5 |
| `alembic/versions/t1rip0000001_trips.py` | revision 3 | 5 |
| `app/services/sheet_import/{__init__,parse,write}.py`, `scripts/{__init__,import_sheet}.py` | importer | 6 |
| `frontend/src/lib/{labels,grouping,status,departures,trips}.js` + tests | pure display logic | 3 |
| `frontend/src/components/{Grid,Checklist,Cell,RowMenu,ConfirmDialog,EvictDialog,States}.jsx`, `frontend/src/hooks/useLongPress.js`, `frontend/src/pages/{PackingList,PackingLists,Options}.jsx`, `frontend/src/App.jsx` | sheet UI per §1a, zh-TW | 7 |
| `frontend/src/pages/Transport.jsx` | Transportation page | 8 |
| `frontend/src/pages/Trip.jsx` | This time page | 9 |

Task order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10. Tasks 3 and 4 are independent of each other; everything else is sequential.

---

### Task 1: Packing item detail, need and location

**Files:**
- Modify: `app/constants.py`, `app/models/packing_item.py`, `app/schemas/packing_item.py`, `app/services/domain/packing.py`, `app/routers/packing_item.py`, `app/routers/label_option.py`
- Create: `app/services/domain/labels.py`, `alembic/versions/p2acking0002_item_detail_need_location.py`
- Test: `tests/api/test_packing_item_router.py`, `tests/api/test_label_option_router.py`, `tests/api/test_packing_list_router.py`, `tests/test_migrations_build_the_schema.py`
- Docs: `docs/data-model.md`, `docs/api.md`, `docs/business-rules.md`

**Interfaces:**
- Produces: `Need` enum (`need`, `bring`, `buy`); `LabelKind.LOCATION = "location"`; `PackingItem.detail/need/location`; `app.services.domain.labels` exporting `remember_label(db, kind, value)`, `remember_item_labels(db, item)`, `count_using(db, option) -> int`, `rename_option(db, option, new_value) -> int`, and `COLUMN_FOR_KIND: dict[LabelKind, InstrumentedAttribute]`. `packing.py` no longer exports the label functions.

- [ ] **Step 1: Write the failing tests**

Append to `tests/api/test_packing_item_router.py`:

```python
def test_an_item_carries_detail_need_and_location(client, packing_list):
    response = add_item(
        client, packing_list, name="鑰匙", detail="家鑰匙", need="bring", location="彰化"
    )
    assert response.status_code == 201
    body = response.json()
    assert (body["detail"], body["need"], body["location"]) == ("家鑰匙", "bring", "彰化")


def test_need_may_be_left_blank(client, packing_list):
    assert add_item(client, packing_list).json()["need"] is None


def test_an_unknown_need_is_a_422_not_a_500(client, packing_list):
    assert add_item(client, packing_list, need="borrow").status_code == 422


def test_every_declared_need_is_accepted(client, packing_list):
    # The mirror of the refusal above.
    for need in ("need", "bring", "buy"):
        assert add_item(client, packing_list, need=need).status_code == 201


def test_the_need_constraint_holds_when_the_schema_is_bypassed(db_session, packing_list):
    from sqlalchemy.exc import IntegrityError

    db_session.add(PackingItem(list_id=packing_list.id, name="x", need="borrow"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_saving_an_item_remembers_its_location(client, packing_list):
    add_item(client, packing_list, location="新北")
    values = [row["value"] for row in client.get("/api/label-options?kind=location").json()]
    assert values == ["新北"]
```

Append to `tests/api/test_label_option_router.py` (reuse that file's existing list fixture/helper names — read the file first; the fixture below assumes one called `packing_list`, create it the same way `test_packing_item_router.py` does if absent):

```python
def test_renaming_a_location_rewrites_the_items_using_it(client, packing_list):
    client.post(f"/api/packing-lists/{packing_list.id}/items", json={"name": "a", "location": "新北"})
    option = client.get("/api/label-options?kind=location").json()[0]
    assert option["usage_count"] == 1
    client.patch(f"/api/label-options/{option['id']}", json={"value": "台北"})
    items = client.get(f"/api/packing-lists/{packing_list.id}").json()["items"]
    assert items[0]["location"] == "台北"
```

Append to `tests/api/test_packing_list_router.py` (read the file for its existing copy test and fixtures; add alongside it):

```python
def test_a_copy_carries_detail_need_and_location(client):
    source = client.post("/api/packing-lists", json={"name": "src", "saved": True}).json()
    client.post(
        f"/api/packing-lists/{source['id']}/items",
        json={"name": "鑰匙", "detail": "家鑰匙", "need": "bring", "location": "彰化", "status": "packed"},
    )
    copy = client.post(
        "/api/packing-lists", json={"name": "copy", "saved": True, "copy_from_id": source["id"]}
    ).json()
    item = copy["items"][0]
    assert (item["detail"], item["need"], item["location"]) == ("家鑰匙", "bring", "彰化")
    assert item["status"] == "not_packed"
```

Add to `tests/test_migrations_build_the_schema.py` a downgrade proof (the file has a `scratch_database` fixture; reuse it):

```python
def test_the_chain_downgrades_to_base_and_back(scratch_database):
    env = {**os.environ, "DATABASE_URL": scratch_database}
    for command in (["upgrade", "head"], ["downgrade", "base"], ["upgrade", "head"]):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *command],
            cwd=ROOT, env=env, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
```

(Read the file first: use its actual names for the root path and the URL the fixture yields; if `os`/`ROOT` are named differently, use those.)

- [ ] **Step 2: Run them to see them fail**

Run: `PYTEST tests/api/test_packing_item_router.py tests/api/test_label_option_router.py tests/api/test_packing_list_router.py -q`
Expected: FAIL — `detail`/`need`/`location` unknown (`KeyError` or 201 where 422 expected).

- [ ] **Step 3: Constants**

In `app/constants.py`, update the docstring's "These five" to "These", and add:

```python
class Need(StrEnum):
    """Why an item is on the list — the sheet's 需求 column.

    `BRING` is already owned and taken from the item's location; `BUY` has to
    be bought, at that location; `NEED` is needed with bring-or-buy not yet
    decided. Nullable on the item: a row the question does not apply to.
    """

    NEED = "need"
    BRING = "bring"
    BUY = "buy"
```

and extend `LabelKind`:

```python
class LabelKind(StrEnum):
    CATEGORY = "category"
    BAG = "bag"
    LOCATION = "location"
```

- [ ] **Step 4: Model**

In `app/models/packing_item.py` import `Need`, add to `__table_args__`:

```python
        CheckConstraint(in_clause("need", Need, nullable=True), name="ck_packing_item_need"),
```

and after `name`:

```python
    # The sheet's column C: a variant (家鑰匙 under 鑰匙) or a description
    # (long c-c beside bed). Items sharing a name are grouped on screen; each
    # is packed on its own.
    detail: Mapped[str | None] = mapped_column(String, nullable=True)
```

and after `bag`:

```python
    # Open, suggested by `label_option` like category and bag.
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    need: Mapped[str | None] = mapped_column(String, nullable=True)
```

- [ ] **Step 5: Migration**

Create `alembic/versions/p2acking0002_item_detail_need_location.py`:

```python
"""packing item detail, need and location

The three columns the owner's sheet has and the first packing revision did not:
column C (a variant or description under an item's name), 需求, and 取得地點.
`label_option.kind` widens to take `location`, so a place typed once is
suggested afterwards like a category is.

Revision ID: p2acking0002
Revises: p1acking0001
Create Date: 2026-09-30

"""

import sqlalchemy as sa

from alembic import op

revision = "p2acking0002"
down_revision = "p1acking0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("packing_item", sa.Column("detail", sa.String(), nullable=True))
    op.add_column("packing_item", sa.Column("location", sa.String(), nullable=True))
    op.add_column("packing_item", sa.Column("need", sa.String(), nullable=True))
    op.create_check_constraint(
        "ck_packing_item_need",
        "packing_item",
        "need IS NULL OR need IN ('need', 'bring', 'buy')",
    )
    op.drop_constraint("ck_label_option_kind", "label_option", type_="check")
    op.create_check_constraint(
        "ck_label_option_kind", "label_option", "kind IN ('category', 'bag', 'location')"
    )


def downgrade() -> None:
    # The narrower constraint would refuse the rows this revision allowed.
    op.execute("DELETE FROM label_option WHERE kind = 'location'")
    op.drop_constraint("ck_label_option_kind", "label_option", type_="check")
    op.create_check_constraint(
        "ck_label_option_kind", "label_option", "kind IN ('category', 'bag')"
    )
    op.drop_constraint("ck_packing_item_need", "packing_item", type_="check")
    op.drop_column("packing_item", "need")
    op.drop_column("packing_item", "location")
    op.drop_column("packing_item", "detail")
```

- [ ] **Step 6: Schemas**

In `app/schemas/packing_item.py` import `Need`; in `PackingItemBase` after `name`: `detail: str | None = None`; after `bag`: `location: str | None = None` and `need: Need | None = None`. Add the same three (all `| None = None`) to `PackingItemUpdate`.

- [ ] **Step 7: Move label rules to `labels.py`**

Create `app/services/domain/labels.py` holding the "Common options" section currently at the bottom of `packing.py` (move its comment block too), generalised from a column *name* to a column *attribute* so a later kind can point at another table:

```python
"""Common options: remembered values behind the free-text fields.

`label_option` rows are suggestions. The row that uses a value holds the text
itself and may always carry a value that is not among them — which is what
makes a rename a rewrite rather than a repointing. Each kind suggests values
for exactly one column, named in `COLUMN_FOR_KIND`.
"""

from sqlalchemy import func, select, update
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.constants import LabelKind
from app.models import LabelOption, PackingItem

#: Which column each kind of option suggests values for.
COLUMN_FOR_KIND: dict[LabelKind, InstrumentedAttribute] = {
    LabelKind.CATEGORY: PackingItem.category,
    LabelKind.BAG: PackingItem.bag,
    LabelKind.LOCATION: PackingItem.location,
}


def remember_label(db: Session, kind: LabelKind, value: str | None) -> None:
    """Record a typed value as a suggestion, if it is not one already."""
    if not value:
        return
    already = db.execute(
        select(LabelOption.id).where(LabelOption.kind == kind, LabelOption.value == value)
    ).first()
    if already:
        return
    highest = db.execute(
        select(func.max(LabelOption.position)).where(LabelOption.kind == kind)
    ).scalar()
    db.add(LabelOption(kind=kind, value=value, position=0 if highest is None else highest + 1))
    db.flush()


def remember_item_labels(db: Session, item: PackingItem) -> None:
    """Record every free-text value an item carries."""
    remember_label(db, LabelKind.CATEGORY, item.category)
    remember_label(db, LabelKind.BAG, item.bag)
    remember_label(db, LabelKind.LOCATION, item.location)


def count_using(db: Session, option: LabelOption) -> int:
    """How many rows carry this option's value, so a rename can say so first."""
    column = COLUMN_FOR_KIND[LabelKind(option.kind)]
    return db.execute(
        select(func.count()).select_from(column.class_).where(column == option.value)
    ).scalar_one()


def rename_option(db: Session, option: LabelOption, new_value: str) -> int:
    """Rename an option, rewriting every row that used it. Returns how many.

    Renaming onto a value that already exists is a **merge**: the rows are
    rewritten either way, and then the source option is deleted rather than
    updated, because the unique constraint on (kind, value) would refuse the
    update outright.
    """
    if new_value == option.value:
        return 0
    column = COLUMN_FOR_KIND[LabelKind(option.kind)]
    rewritten = db.execute(
        update(column.class_).where(column == option.value).values({column.key: new_value})
    ).rowcount
    collision = db.execute(
        select(LabelOption).where(
            LabelOption.kind == option.kind,
            LabelOption.value == new_value,
            LabelOption.id != option.id,
        )
    ).scalar_one_or_none()
    if collision is not None:
        db.delete(option)
    else:
        option.value = new_value
    db.flush()
    return rewritten
```

Delete that section from `packing.py` (and the now-unused imports `update`, `LabelKind`, `LabelOption`). Update imports: `app/routers/packing_item.py` → `from app.services.domain.labels import remember_item_labels`; `app/routers/label_option.py` → `from app.services.domain.labels import count_using, rename_option` and rename the call `count_items_using` → `count_using`. Grep for any other importer: `grep -rn "count_items_using\|remember_item_labels\|rename_option\|_COLUMN_FOR_KIND" app tests`.

- [ ] **Step 8: Copy carries the new fields**

In `copy_items` in `packing.py`, add to the "Carried" block: `detail=item.detail,`, `need=item.need,`, `location=item.location,`.

- [ ] **Step 9: Run the tests**

Run: `PYTEST tests/ -q`
Expected: all pass, including the downgrade round trip and `test_there_is_exactly_one_head`.

- [ ] **Step 10: Docs**

- `docs/data-model.md`: add `detail`, `location`, `need` rows to the `packing_item` table; add `ck_packing_item_need` (with the null-arm note, as for `ck_packing_list_leg`); `label_option.kind` becomes `category`, `bag` or `location`; the mermaid edge label becomes "category, bag and location". Update "Last verified" to 2026-09-30.
- `docs/api.md`: item fields gain `detail`, `need` (`need`/`bring`/`buy`/null), `location`.
- `docs/business-rules.md`: copy table's Carries column gains `detail`, `need`, `location`; "Common options" mentions `location` wherever it lists `category` and `bag`; add a short "Need and location" section with the meaning of the three values from the constant's docstring.

- [ ] **Step 11: Lint and commit**

```bash
venv/Scripts/ruff check .
git add app/constants.py app/models/packing_item.py app/schemas/packing_item.py app/services/domain/packing.py app/services/domain/labels.py app/routers/packing_item.py app/routers/label_option.py alembic/versions/p2acking0002_item_detail_need_location.py tests/api/test_packing_item_router.py tests/api/test_label_option_router.py tests/api/test_packing_list_router.py tests/test_migrations_build_the_schema.py docs/data-model.md docs/api.md docs/business-rules.md
git commit -m "feat: packing items carry a detail, a need and a location" -- <the same paths>
```

---

### Task 2: Insert after an item, and reset a list's status

**Files:**
- Modify: `app/services/domain/packing.py`, `app/schemas/packing_item.py`, `app/routers/packing_item.py`, `app/routers/packing_list.py`
- Test: `tests/api/test_packing_item_router.py`, `tests/api/test_packing_list_router.py`
- Docs: `docs/api.md`, `docs/business-rules.md`

**Interfaces:**
- Consumes: Task 1's model.
- Produces: `insert_after(db, after: PackingItem) -> int` (returns the position for the new item, having shifted later items); `reset_list(db, packing_list) -> None`; `PackingItemCreate.after_id: int | None`; `POST /api/packing-lists/{id}/reset` → `PackingListResponse`.

- [ ] **Step 1: Failing tests**

Append to `tests/api/test_packing_item_router.py`:

```python
def positions(client, packing_list):
    items = client.get(f"/api/packing-lists/{packing_list.id}").json()["items"]
    return [(item["name"], item.get("detail"), item["position"]) for item in items]


def test_after_id_inserts_directly_after_and_shifts_later_items(client, packing_list):
    keys = add_item(client, packing_list, name="鑰匙", detail="家鑰匙").json()
    add_item(client, packing_list, name="眼鏡")
    add_item(client, packing_list, name="鑰匙", detail="宿舍鑰匙", after_id=keys["id"])
    assert positions(client, packing_list) == [
        ("鑰匙", "家鑰匙", 0),
        ("鑰匙", "宿舍鑰匙", 1),
        ("眼鏡", None, 2),
    ]


def test_after_id_does_not_move_another_lists_items(client, db_session, packing_list):
    other = PackingList(name="other")
    db_session.add(other)
    db_session.commit()
    add_item(client, other, name="far")
    first = add_item(client, packing_list, name="a").json()
    add_item(client, packing_list, name="b", after_id=first["id"])
    assert positions(client, other) == [("far", None, 0)]


def test_after_id_from_another_list_is_a_404(client, db_session, packing_list):
    other = PackingList(name="other")
    db_session.add(other)
    db_session.commit()
    foreign = add_item(client, other, name="far").json()
    assert add_item(client, packing_list, name="x", after_id=foreign["id"]).status_code == 404
    # Mirror: the same id on its own list is accepted.
    assert add_item(client, other, name="y", after_id=foreign["id"]).status_code == 201
```

Append to `tests/api/test_packing_list_router.py`:

```python
def test_a_reset_unpacks_clears_counts_and_checks_but_leaves_no_need_alone(client):
    lst = client.post("/api/packing-lists", json={"name": "r", "saved": True}).json()
    url = f"/api/packing-lists/{lst['id']}/items"
    client.post(url, json={"name": "packed", "status": "packed", "quantity": 2,
                           "quantity_packed": 2, "needs_double_check": True, "double_checked": True})
    # Load-bearing: without a no_need item the test cannot tell "left alone"
    # from "never there".
    client.post(url, json={"name": "skip", "status": "no_need"})
    other = client.post("/api/packing-lists", json={"name": "o", "saved": True}).json()
    client.post(f"/api/packing-lists/{other['id']}/items", json={"name": "keep", "status": "packed"})

    response = client.post(f"/api/packing-lists/{lst['id']}/reset")
    assert response.status_code == 200
    by_name = {item["name"]: item for item in response.json()["items"]}
    assert by_name["packed"]["status"] == "not_packed"
    assert by_name["packed"]["quantity_packed"] == 0
    assert by_name["packed"]["double_checked"] is False
    assert by_name["packed"]["needs_double_check"] is True  # definition, not state
    assert by_name["skip"]["status"] == "no_need"
    other_items = client.get(f"/api/packing-lists/{other['id']}").json()["items"]
    assert other_items[0]["status"] == "packed"


def test_resetting_a_missing_list_is_a_404(client):
    assert client.post("/api/packing-lists/999999/reset").status_code == 404
```

- [ ] **Step 2: Run to see them fail**

Run: `PYTEST tests/api/test_packing_item_router.py tests/api/test_packing_list_router.py -q`
Expected: FAIL — `after_id` ignored (positions wrong) and reset 404/405.

- [ ] **Step 3: Domain**

In `app/services/domain/packing.py` (import `update` from sqlalchemy again):

```python
def insert_after(db: Session, after: PackingItem) -> int:
    """Make room directly after `after` on its own list; return that position.

    Every later item on the SAME list shifts down by one, in the caller's
    transaction, so positions stay contiguous and a variant lands under the
    row it was added from.
    """
    db.execute(
        update(PackingItem)
        .where(PackingItem.list_id == after.list_id, PackingItem.position > after.position)
        .values(position=PackingItem.position + 1)
    )
    return after.position + 1


def reset_list(db: Session, packing_list: PackingList) -> None:
    """重設狀態: the copy rule's reset half, minus `no_need`.

    `no_need` is a choice about the list rather than progress through it, so
    it survives. `needs_double_check` is definition and survives too; only
    whether the check happened is cleared.
    """
    db.execute(
        update(PackingItem)
        .where(PackingItem.list_id == packing_list.id)
        .values(quantity_packed=0, double_checked=False)
    )
    db.execute(
        update(PackingItem)
        .where(PackingItem.list_id == packing_list.id, PackingItem.status == Status.PACKED)
        .values(status=Status.NOT_PACKED)
    )
    db.flush()
```

- [ ] **Step 4: Schema and routers**

`PackingItemCreate` gains `after_id: int | None = None` (keep it off `PackingItemBase` so it is not echoed in responses). In `app/routers/packing_item.py` `create`:

```python
    fields = payload.model_dump(exclude={"after_id"})
    if payload.after_id is None:
        position = _next_position(db, list_id)
    else:
        after = db.get(PackingItem, payload.after_id)
        if after is None or after.list_id != list_id:
            raise HTTPException(status_code=404, detail="Item to insert after not found on this list.")
        position = insert_after(db, after)
    item = PackingItem(list_id=list_id, position=position, **fields)
```

In `app/routers/packing_list.py` add (import `reset_list`):

```python
@router.post("/{list_id}/reset", response_model=PackingListResponse)
def reset(list_id: int, db: Session = Depends(get_db)):
    packing_list = _get(db, list_id)
    reset_list(db, packing_list)
    db.commit()
    db.expire_all()
    return read(list_id, db)
```

- [ ] **Step 5: Run the tests**

Run: `PYTEST tests/ -q` — Expected: PASS.

- [ ] **Step 6: Docs**

`docs/api.md`: items table gains `after_id` on create (404 when it names no item on that list) and the position paragraph says "one past the end, or directly after `after_id`, shifting later items"; lists table gains `POST /api/packing-lists/{id}/reset`. `docs/business-rules.md`: a "重設狀態" section with the rule from `reset_list`'s docstring.

- [ ] **Step 7: Commit**

```bash
git commit -m "feat: insert an item after another, and reset a list's status" -- app/services/domain/packing.py app/schemas/packing_item.py app/routers/packing_item.py app/routers/packing_list.py tests/api/test_packing_item_router.py tests/api/test_packing_list_router.py docs/api.md docs/business-rules.md
```
(`git add` the same paths first.)

---

### Task 3: Frontend display logic (labels, grouping, status, departures, trips)

Pure modules with vitest coverage; no component changes yet. Independent of Task 4.

**Files:**
- Create: `frontend/src/lib/labels.js`, `frontend/src/lib/labels.test.js`, `frontend/src/lib/grouping.js`, `frontend/src/lib/grouping.test.js`, `frontend/src/lib/status.js`, `frontend/src/lib/status.test.js`, `frontend/src/lib/departures.js`, `frontend/src/lib/departures.test.js`, `frontend/src/lib/trips.js`, `frontend/src/lib/trips.test.js`
- Modify: `frontend/src/lib/timing.js` (drop `TIMING_LABELS`, which moves to `labels.js`), `frontend/src/components/Grid.jsx` (import `TIMING_LABELS` from `../lib/labels` so the build stays green)

**Interfaces — Produces:**
- `labels.js`: `STATUS_LABELS`, `CHECK_LABELS`, `TIMING_LABELS`, `NEED_LABELS`, `DAY_TYPE_LABELS`, `BUCKET_LABELS`, `LEG_LABELS`, `LABEL_KIND_LABELS`, `BOOKING_LABELS`, `NEEDS = ['need','bring','buy']`, `CHECK_STATES = ['off','needed','done']`, `checkState(item)`, `CHECK_FIELDS` (state → `{needs_double_check, double_checked}`).
- `grouping.js`: `groupRuns(items) -> Array<{ item, showCategory: boolean, showName: boolean }>` ; `groupForChecklist(items) -> Array<{ key, name, items }>`.
- `status.js`: `tapStatus(status) -> status`.
- `departures.js`: `BUCKETS`, `bucketOf('HH:MM[:SS]')`, `groupByBucket(departures) -> {morning:[],midday:[],afternoon:[],evening:[]}`, `dayTypeOf(date)`, `nextDeparture(departures, now) -> departure|null`, `parseDepartureInput(text) -> {time, irregular}|null`, `formatDeparture(d) -> '*13:40'`.
- `trips.js`: `TAIPEI = 'Asia/Taipei'`, `formatDuration(departsAt, arrivesAt) -> '2h53m'`, `formatTaipei(iso) -> 'Thu 09/24 18:06'`, `taipeiInputValue(iso) -> 'YYYY-MM-DDTHH:mm'`, `fromTaipeiInput(value) -> ISO string with +08:00`.

- [ ] **Step 1: Write the tests**

`frontend/src/lib/labels.test.js`:

```js
import { describe, expect, it } from 'vitest'

import {
  CHECK_LABELS, CHECK_STATES, DAY_TYPE_LABELS, NEED_LABELS, NEEDS,
  STATUS_LABELS, TIMING_LABELS, checkState,
} from './labels'
import { TIMINGS } from './timing'

describe('labels', () => {
  it('has a display string for every stored value', () => {
    for (const s of ['not_packed', 'packed', 'no_need']) expect(STATUS_LABELS[s]).toBeTruthy()
    for (const t of TIMINGS) expect(TIMING_LABELS[t]).toBeTruthy()
    for (const n of NEEDS) expect(NEED_LABELS[n]).toBeTruthy()
    for (const c of CHECK_STATES) expect(CHECK_LABELS[c]).toBeTruthy()
    for (const d of ['weekday', 'holiday']) expect(DAY_TYPE_LABELS[d]).toBeTruthy()
  })

  it('uses the sheet words', () => {
    expect(STATUS_LABELS).toEqual({ not_packed: '未打包', packed: '已打包', no_need: '不需打包' })
    expect(TIMING_LABELS).toEqual({
      whenever: '隨時', night_before: '出發前晚', day_of: '出發當天', just_before: '出發前',
    })
    expect(NEED_LABELS).toEqual({ need: '需要', bring: '需帶', buy: '需買' })
    expect(CHECK_LABELS).toEqual({ off: '不需確認', needed: '未確認', done: '確認' })
  })

  it('derives the check state from the two fields', () => {
    expect(checkState({ needs_double_check: false, double_checked: false })).toBe('off')
    expect(checkState({ needs_double_check: true, double_checked: false })).toBe('needed')
    expect(checkState({ needs_double_check: true, double_checked: true })).toBe('done')
  })
})
```

`frontend/src/lib/grouping.test.js`:

```js
import { describe, expect, it } from 'vitest'

import { groupForChecklist, groupRuns } from './grouping'

const item = (id, category, name, detail = null) => ({ id, category, name, detail, position: id })

describe('groupRuns', () => {
  it('blanks repeated category and name, like the sheet', () => {
    const rows = groupRuns([
      item(1, '重要', '錢包'),
      item(2, '重要', '鑰匙', '家鑰匙'),
      item(3, '重要', '鑰匙', '宿舍鑰匙'),
      item(4, '3C', '鑰匙'),
    ])
    expect(rows.map((r) => [r.item.id, r.showCategory, r.showName])).toEqual([
      [1, true, true],
      [2, false, true],
      [3, false, false],
      [4, true, true], // a new category restarts the name run too
    ])
  })

  it('treats blank categories as equal to each other', () => {
    const rows = groupRuns([item(1, null, 'a'), item(2, null, 'a', 'b')])
    expect(rows.map((r) => r.showCategory)).toEqual([true, false])
  })
})

describe('groupForChecklist', () => {
  it('puts consecutive same-name items under one heading', () => {
    const groups = groupForChecklist([
      item(1, '重要', '鑰匙', '家鑰匙'),
      item(2, '重要', '鑰匙', '宿舍鑰匙'),
      item(3, '重要', '眼鏡'),
    ])
    expect(groups.map((g) => [g.name, g.items.map((i) => i.id)])).toEqual([
      ['鑰匙', [1, 2]],
      ['眼鏡', [3]],
    ])
  })
})
```

`frontend/src/lib/status.test.js`:

```js
import { describe, expect, it } from 'vitest'

import { tapStatus } from './status'

describe('tapStatus', () => {
  it('toggles between not packed and packed', () => {
    expect(tapStatus('not_packed')).toBe('packed')
    expect(tapStatus('packed')).toBe('not_packed')
  })
  it('brings no_need back to not packed rather than cycling through it', () => {
    expect(tapStatus('no_need')).toBe('not_packed')
  })
})
```

`frontend/src/lib/departures.test.js`:

```js
import { describe, expect, it } from 'vitest'

import {
  bucketOf, dayTypeOf, formatDeparture, groupByBucket, nextDeparture, parseDepartureInput,
} from './departures'

describe('bucketOf', () => {
  it('splits the day at 12:00, 14:00 and 18:00', () => {
    expect(bucketOf('11:59')).toBe('morning')
    expect(bucketOf('12:00')).toBe('midday')
    expect(bucketOf('13:59:00')).toBe('midday')
    expect(bucketOf('14:00')).toBe('afternoon')
    expect(bucketOf('17:59')).toBe('afternoon')
    expect(bucketOf('18:00')).toBe('evening')
  })
})

describe('groupByBucket', () => {
  it('sorts within a bucket', () => {
    const groups = groupByBucket([{ time: '08:40' }, { time: '07:00' }, { time: '19:40' }])
    expect(groups.morning.map((d) => d.time)).toEqual(['07:00', '08:40'])
    expect(groups.evening.map((d) => d.time)).toEqual(['19:40'])
    expect(groups.midday).toEqual([])
  })
})

describe('dayTypeOf', () => {
  it('treats Saturday and Sunday as holidays', () => {
    expect(dayTypeOf(new Date(2026, 8, 26))).toBe('holiday') // Sat
    expect(dayTypeOf(new Date(2026, 8, 27))).toBe('holiday') // Sun
    expect(dayTypeOf(new Date(2026, 8, 28))).toBe('weekday') // Mon
  })
})

describe('nextDeparture', () => {
  const deps = [
    { id: 1, day_type: 'holiday', time: '07:00:00' },
    { id: 2, day_type: 'holiday', time: '13:40:00' },
    { id: 3, day_type: 'weekday', time: '09:00:00' },
  ]
  it('is the first of today\'s day type at or after now', () => {
    expect(nextDeparture(deps, new Date(2026, 8, 26, 8, 0)).id).toBe(2)
    expect(nextDeparture(deps, new Date(2026, 8, 26, 13, 40)).id).toBe(2)
  })
  it('is null once today\'s last one has gone', () => {
    expect(nextDeparture(deps, new Date(2026, 8, 26, 20, 0))).toBeNull()
  })
})

describe('parseDepartureInput / formatDeparture', () => {
  it('reads the sheet notation', () => {
    expect(parseDepartureInput('*13:40')).toEqual({ time: '13:40', irregular: true })
    expect(parseDepartureInput(' 7:05 ')).toEqual({ time: '07:05', irregular: false })
    expect(parseDepartureInput('25:00')).toBeNull()
    expect(parseDepartureInput('soon')).toBeNull()
  })
  it('writes it back', () => {
    expect(formatDeparture({ time: '13:40:00', irregular: true })).toBe('*13:40')
    expect(formatDeparture({ time: '07:05:00', irregular: false })).toBe('7:05')
  })
})
```

`frontend/src/lib/trips.test.js`:

```js
import { describe, expect, it } from 'vitest'

import { formatDuration, formatTaipei, fromTaipeiInput, taipeiInputValue } from './trips'

describe('formatDuration', () => {
  it('matches the sheet format', () => {
    expect(formatDuration('2026-09-24T18:06:00+08:00', '2026-09-24T20:59:00+08:00')).toBe('2h53m')
    expect(formatDuration('2026-09-28T12:15:00+08:00', '2026-09-28T14:23:00+08:00')).toBe('2h08m')
    expect(formatDuration('2026-09-28T12:15:00+08:00', '2026-09-28T12:22:00+08:00')).toBe('7m')
  })
})

describe('Taipei conversions', () => {
  it('shows a UTC instant in Taipei time', () => {
    expect(formatTaipei('2026-09-24T10:06:00Z')).toBe('Thu 09/24 18:06')
  })
  it('round-trips an input value', () => {
    expect(taipeiInputValue('2026-09-23T16:30:00Z')).toBe('2026-09-24T00:30')
    expect(fromTaipeiInput('2026-09-24T00:30')).toBe('2026-09-24T00:30:00+08:00')
  })
})
```

- [ ] **Step 2: Run to see them fail**

Run: `cd frontend && npm test` — Expected: FAIL, modules not found.

- [ ] **Step 3: Implement**

`frontend/src/lib/labels.js`:

```js
/**
 * Every display string for a stored value, in the owner's sheet's own words.
 *
 * Stored values stay English enum text; this is the one place they become
 * what the screen says. A value missing here is a blank on screen, which is
 * why labels.test.js walks every vocabulary.
 */

export const STATUS_LABELS = { not_packed: '未打包', packed: '已打包', no_need: '不需打包' }

export const TIMING_LABELS = {
  whenever: '隨時',
  night_before: '出發前晚',
  day_of: '出發當天',
  just_before: '出發前',
}

export const NEEDS = ['need', 'bring', 'buy']
export const NEED_LABELS = { need: '需要', bring: '需帶', buy: '需買' }

/** Double Check is two fields; on screen it is one of three states. */
export const CHECK_STATES = ['off', 'needed', 'done']
export const CHECK_LABELS = { off: '不需確認', needed: '未確認', done: '確認' }
export const CHECK_FIELDS = {
  off: { needs_double_check: false, double_checked: false },
  needed: { needs_double_check: true, double_checked: false },
  done: { needs_double_check: true, double_checked: true },
}
export function checkState(item) {
  if (!item.needs_double_check) return 'off'
  return item.double_checked ? 'done' : 'needed'
}

export const DAY_TYPE_LABELS = { weekday: '平日', holiday: '假日' }
export const BUCKET_LABELS = { morning: '早', midday: '中', afternoon: '下午', evening: '晚' }
export const LEG_LABELS = { outbound: '去程', return: '回程' }
export const LABEL_KIND_LABELS = {
  category: '類別', bag: '包包', location: '取得地點', ticket_type: '車票類型',
}
export const BOOKING_LABELS = { booked: '已訂票', paid: '付款', collected: '取票' }
```

`frontend/src/lib/grouping.js`:

```js
/**
 * The sheet's visual grouping: a category or a name is written once, on the
 * first row of a run, and left blank beneath — exactly how the owner's Google
 * Sheet reads. Only meaningful in position order; the Grid turns it off under
 * any other sort, where a blank cell would be ambiguous.
 */

const same = (a, b) => (a ?? '') === (b ?? '')

export function groupRuns(items) {
  return items.map((item, index) => {
    const previous = items[index - 1]
    const showCategory = !previous || !same(previous.category, item.category)
    const showName = showCategory || !same(previous.name, item.name)
    return { item, showCategory, showName }
  })
}

/** Consecutive items sharing a category and name, as one heading each. */
export function groupForChecklist(items) {
  const groups = []
  for (const { item, showName } of groupRuns(items)) {
    if (showName) groups.push({ key: item.id, name: item.name, items: [item] })
    else groups[groups.length - 1].items.push(item)
  }
  return groups
}
```

`frontend/src/lib/status.js`:

```js
/**
 * One tap: 未打包 ⇄ 已打包. 不需打包 is set from the row menu, never by
 * tapping; tapping a 不需打包 row brings it back to 未打包.
 */
export function tapStatus(status) {
  return status === 'not_packed' ? 'packed' : 'not_packed'
}
```

`frontend/src/lib/departures.js`:

```js
/**
 * Departure times: the sheet's 早/中/下午/晚 columns, computed from the clock.
 *
 * `now` is always a parameter, never a `new Date()` inside, so tests can stand
 * on a boundary. Weekday vs holiday is Monday–Friday vs Saturday–Sunday;
 * public holidays are not modelled.
 */

export const BUCKETS = ['morning', 'midday', 'afternoon', 'evening']

const minutes = (time) => {
  const [h, m] = time.split(':').map(Number)
  return h * 60 + m
}

export function bucketOf(time) {
  const m = minutes(time)
  if (m < 12 * 60) return 'morning'
  if (m < 14 * 60) return 'midday'
  if (m < 18 * 60) return 'afternoon'
  return 'evening'
}

export function groupByBucket(departures) {
  const groups = Object.fromEntries(BUCKETS.map((b) => [b, []]))
  const sorted = [...departures].sort((a, b) => minutes(a.time) - minutes(b.time))
  for (const d of sorted) groups[bucketOf(d.time)].push(d)
  return groups
}

export function dayTypeOf(date) {
  const day = date.getDay()
  return day === 0 || day === 6 ? 'holiday' : 'weekday'
}

export function nextDeparture(departures, now) {
  const today = dayTypeOf(now)
  const current = now.getHours() * 60 + now.getMinutes()
  const candidates = departures
    .filter((d) => d.day_type === today && minutes(d.time) >= current)
    .sort((a, b) => minutes(a.time) - minutes(b.time))
  return candidates[0] ?? null
}

/** "*13:40" → irregular 13:40. The sheet's own notation, so typing it works. */
export function parseDepartureInput(text) {
  const match = /^\s*(\*)?\s*(\d{1,2}):(\d{2})\s*$/.exec(text)
  if (!match) return null
  const [, star, h, m] = match
  if (Number(h) > 23 || Number(m) > 59) return null
  return { time: `${h.padStart(2, '0')}:${m}`, irregular: Boolean(star) }
}

export function formatDeparture({ time, irregular }) {
  const [h, m] = time.split(':')
  return `${irregular ? '*' : ''}${Number(h)}:${m}`
}
```

`frontend/src/lib/trips.js`:

```js
/**
 * Leg times. Stored as instants; always shown and entered in Asia/Taipei,
 * whatever timezone the viewing device is in.
 */

export const TAIPEI = 'Asia/Taipei'

export function formatDuration(departsAt, arrivesAt) {
  const total = Math.round((new Date(arrivesAt) - new Date(departsAt)) / 60000)
  const h = Math.floor(total / 60)
  const m = total % 60
  return h ? `${h}h${String(m).padStart(2, '0')}m` : `${m}m`
}

function parts(iso) {
  const fmt = new Intl.DateTimeFormat('en-US', {
    timeZone: TAIPEI, weekday: 'short', year: 'numeric', month: '2-digit',
    day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  })
  return Object.fromEntries(fmt.formatToParts(new Date(iso)).map((p) => [p.type, p.value]))
}

export function formatTaipei(iso) {
  const p = parts(iso)
  return `${p.weekday} ${p.month}/${p.day} ${p.hour}:${p.minute}`
}

export function taipeiInputValue(iso) {
  const p = parts(iso)
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`
}

/** Taiwan has no daylight saving, so the offset is always +08:00. */
export function fromTaipeiInput(value) {
  return `${value}:00+08:00`
}
```

In `frontend/src/lib/timing.js` delete `TIMING_LABELS`; in `Grid.jsx` change the import to `import { TIMINGS } from '../lib/timing'` and `import { TIMING_LABELS } from '../lib/labels'`.

- [ ] **Step 4: Run**

Run: `cd frontend && npm test && npm run lint && npm run build` — Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: display vocabulary and grouping, status and timetable logic for the sheet UI" -- frontend/src/lib/labels.js frontend/src/lib/labels.test.js frontend/src/lib/grouping.js frontend/src/lib/grouping.test.js frontend/src/lib/status.js frontend/src/lib/status.test.js frontend/src/lib/departures.js frontend/src/lib/departures.test.js frontend/src/lib/trips.js frontend/src/lib/trips.test.js frontend/src/lib/timing.js frontend/src/components/Grid.jsx
```

---

### Task 4: Transport routes, options and departures (backend)

**Files:**
- Modify: `app/constants.py`, `app/models/__init__.py`, `app/main.py`
- Create: `app/models/transport.py`, `app/schemas/transport.py`, `app/routers/transport.py`, `alembic/versions/t1ransport01_transport.py`, `tests/api/test_transport_router.py`
- Docs: `docs/data-model.md`, `docs/api.md`

**Interfaces:**
- Produces: `DayType` (`weekday`, `holiday`); models `TransportRoute`, `TransportOption`, `TransportDeparture`; endpoints below. Response shape `TransportRouteResponse{id, from_place, to_place, notes, position, options: [TransportOptionResponse{id, route_id, mode, advance_ticket, route_map_url, timetable_url, live_url, direction, line_from, line_to, board_at, alight_at, price, duration, headway, notes, position, departures: [TransportDepartureResponse{id, option_id, day_type, time, irregular}]}]}`.

Endpoints (item-style: create under the parent, address alone afterwards):

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/transport-routes` | all routes by `position`, `id`, nested |
| POST | `/api/transport-routes` | 201 |
| GET / PATCH / DELETE | `/api/transport-routes/{id}` | 404 when missing |
| POST | `/api/transport-routes/{route_id}/options` | 201, appended by position |
| PATCH / DELETE | `/api/transport-options/{id}` | |
| POST | `/api/transport-options/{option_id}/departures` | 201; 409 when that (day_type, time) exists |
| PATCH / DELETE | `/api/transport-departures/{id}` | 409 on a PATCH that collides |

- [ ] **Step 1: Failing tests** — `tests/api/test_transport_router.py`:

```python
"""Transport: routes own options, options own departures, and times are rows."""

import pytest


@pytest.fixture
def route(client):
    return client.post(
        "/api/transport-routes", json={"from_place": "彰化火車站", "to_place": "宿舍"}
    ).json()


@pytest.fixture
def option(client, route):
    return client.post(
        f"/api/transport-routes/{route['id']}/options",
        json={"mode": "彰化客運6933A", "board_at": "彰化", "alight_at": "南瑤宮", "price": 22},
    ).json()


def add_departure(client, option, **fields):
    payload = {"day_type": "holiday", "time": "13:40", **fields}
    return client.post(f"/api/transport-options/{option['id']}/departures", json=payload)


def test_a_route_reads_back_with_its_options_and_departures(client, route, option):
    add_departure(client, option, time="07:30")
    add_departure(client, option, time="13:40", irregular=True)
    routes = client.get("/api/transport-routes").json()
    assert [r["from_place"] for r in routes] == ["彰化火車站"]
    opt = routes[0]["options"][0]
    assert opt["mode"] == "彰化客運6933A" and opt["price"] == 22
    assert [(d["time"], d["irregular"]) for d in opt["departures"]] == [
        ("07:30:00", False),
        ("13:40:00", True),
    ]


def test_a_route_without_options_is_allowed(client, route):
    assert client.get(f"/api/transport-routes/{route['id']}").json()["options"] == []


def test_an_option_needs_a_mode(client, route):
    response = client.post(f"/api/transport-routes/{route['id']}/options", json={"mode": ""})
    assert response.status_code == 422


def test_an_unknown_day_type_is_a_422(client, option):
    assert add_departure(client, option, day_type="sunday").status_code == 422
    # Mirror.
    assert add_departure(client, option, day_type="weekday").status_code == 201


def test_a_duplicate_departure_is_a_409(client, option):
    assert add_departure(client, option).status_code == 201
    assert add_departure(client, option).status_code == 409
    # Mirror: same time, other day type, is a different departure.
    assert add_departure(client, option, day_type="weekday").status_code == 201


def test_a_patch_that_collides_is_a_409(client, option):
    add_departure(client, option, time="07:00")
    later = add_departure(client, option, time="08:00").json()
    response = client.patch(f"/api/transport-departures/{later['id']}", json={"time": "07:00"})
    assert response.status_code == 409


def test_deleting_a_route_takes_its_options_and_departures(client, db_session, route, option):
    from app.models import TransportDeparture, TransportOption

    add_departure(client, option)
    assert client.delete(f"/api/transport-routes/{route['id']}").status_code == 204
    assert db_session.query(TransportOption).count() == 0
    assert db_session.query(TransportDeparture).count() == 0


def test_options_append_in_order(client, route, option):
    second = client.post(
        f"/api/transport-routes/{route['id']}/options", json={"mode": "彰化客運6912"}
    ).json()
    assert second["position"] == option["position"] + 1
```

- [ ] **Step 2: Run** `PYTEST tests/api/test_transport_router.py -q` — Expected: FAIL (404s / import errors).

- [ ] **Step 3: Constants, models, migration**

`app/constants.py`:

```python
class DayType(StrEnum):
    """The sheet's 平日 / 假日 split. Public holidays are not modelled."""

    WEEKDAY = "weekday"
    HOLIDAY = "holiday"
```

`app/models/transport.py`:

```python
"""Getting between two places: a route, the ways of doing it, and when they run."""

from datetime import time

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import DayType
from app.database import Base
from app.models.base import TimestampMixin, in_clause


class TransportRoute(Base, TimestampMixin):
    __tablename__ = "transport_route"

    id: Mapped[int] = mapped_column(primary_key=True)
    from_place: Mapped[str] = mapped_column(String, nullable=False)
    to_place: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    options = relationship(
        "TransportOption",
        back_populates="route",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TransportOption.position",
    )


class TransportOption(Base, TimestampMixin):
    """One way of doing a route — a bus line, a train service."""

    __tablename__ = "transport_option"

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[int] = mapped_column(
        ForeignKey("transport_route.id", ondelete="CASCADE", name="fk_transport_option_transport_route"),
        nullable=False,
        index=True,
    )
    mode: Mapped[str] = mapped_column(String, nullable=False)
    advance_ticket: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    route_map_url: Mapped[str | None] = mapped_column(String, nullable=True)
    timetable_url: Mapped[str | None] = mapped_column(String, nullable=True)
    live_url: Mapped[str | None] = mapped_column(String, nullable=True)
    direction: Mapped[str | None] = mapped_column(String, nullable=True)
    # The line's own terminals, and where you actually get on and off. The
    # sheet keeps both because a bus from 台中 to 鹿港 is boarded at 彰化.
    line_from: Mapped[str | None] = mapped_column(String, nullable=True)
    line_to: Mapped[str | None] = mapped_column(String, nullable=True)
    board_at: Mapped[str | None] = mapped_column(String, nullable=True)
    alight_at: Mapped[str | None] = mapped_column(String, nullable=True)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Text, because the sheet's values are ranges ("2h-2h30m").
    duration: Mapped[str | None] = mapped_column(String, nullable=True)
    headway: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    route = relationship("TransportRoute", back_populates="options")
    departures = relationship(
        "TransportDeparture",
        back_populates="option",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="[TransportDeparture.day_type, TransportDeparture.time]",
    )


class TransportDeparture(Base, TimestampMixin):
    """One scheduled time. The sheet's 早/中/下午/晚 columns are computed from it."""

    __tablename__ = "transport_departure"
    __table_args__ = (
        CheckConstraint(in_clause("day_type", DayType), name="ck_transport_departure_day_type"),
        UniqueConstraint("option_id", "day_type", "time", name="uq_transport_departure_option_day_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    option_id: Mapped[int] = mapped_column(
        ForeignKey("transport_option.id", ondelete="CASCADE", name="fk_transport_departure_transport_option"),
        nullable=False,
        index=True,
    )
    day_type: Mapped[str] = mapped_column(String, nullable=False)
    time: Mapped[time] = mapped_column(Time, nullable=False)
    # The sheet's '*': "not always will we have that time".
    irregular: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    option = relationship("TransportOption", back_populates="departures")
```

Note the name clash: the column attribute `time` shadows the imported `time` type inside the class body. Import it as `from datetime import time as clock_time` and annotate `Mapped[clock_time]` to avoid it.

Register in `app/models/__init__.py` (import and `__all__`).

`alembic/versions/t1ransport01_transport.py`: `revision = "t1ransport01"`, `down_revision = "p2acking0002"`, docstring explaining "three tables; times are rows so the four day-part columns cannot drift". `upgrade()` creates the three tables with exactly the columns, server defaults, named constraints and indexes above (`ix_transport_option_route_id`, `ix_transport_departure_option_id`), following `p1acking0001`'s style (explicit `created_at`/`updated_at` with `server_default=sa.text("now()")`, `sa.PrimaryKeyConstraint("id")`, `sa.ForeignKeyConstraint([...], [...], name=..., ondelete="CASCADE")`). `downgrade()` drops indexes then tables, children first. The Task 1 round-trip test and the fixture's `upgrade head` prove the revision: run `PYTEST tests/test_migrations_build_the_schema.py -q`.

- [ ] **Step 4: Schemas** — `app/schemas/transport.py`:

```python
"""Transport going in and coming out."""

from datetime import time

from pydantic import BaseModel, ConfigDict, Field

from app.constants import DayType


class TransportDepartureCreate(BaseModel):
    day_type: DayType
    time: time
    irregular: bool = False


class TransportDepartureUpdate(BaseModel):
    day_type: DayType | None = None
    time: time | None = None
    irregular: bool | None = None


class TransportDepartureResponse(TransportDepartureCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    option_id: int


class TransportOptionBase(BaseModel):
    mode: str = Field(min_length=1)
    advance_ticket: bool = False
    route_map_url: str | None = None
    timetable_url: str | None = None
    live_url: str | None = None
    direction: str | None = None
    line_from: str | None = None
    line_to: str | None = None
    board_at: str | None = None
    alight_at: str | None = None
    price: int | None = Field(default=None, ge=0)
    duration: str | None = None
    headway: str | None = None
    notes: str | None = None


class TransportOptionUpdate(BaseModel):
    mode: str | None = Field(default=None, min_length=1)
    advance_ticket: bool | None = None
    route_map_url: str | None = None
    timetable_url: str | None = None
    live_url: str | None = None
    direction: str | None = None
    line_from: str | None = None
    line_to: str | None = None
    board_at: str | None = None
    alight_at: str | None = None
    price: int | None = Field(default=None, ge=0)
    duration: str | None = None
    headway: str | None = None
    notes: str | None = None
    position: int | None = Field(default=None, ge=0)


class TransportOptionResponse(TransportOptionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    route_id: int
    position: int
    departures: list[TransportDepartureResponse] = []


class TransportRouteBase(BaseModel):
    from_place: str = Field(min_length=1)
    to_place: str = Field(min_length=1)
    notes: str | None = None


class TransportRouteUpdate(BaseModel):
    from_place: str | None = Field(default=None, min_length=1)
    to_place: str | None = Field(default=None, min_length=1)
    notes: str | None = None
    position: int | None = Field(default=None, ge=0)


class TransportRouteResponse(TransportRouteBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    position: int
    options: list[TransportOptionResponse] = []
```

(The field named `time` shadows the type inside the class body too — import `from datetime import time as clock_time` and annotate `time: clock_time`.)

- [ ] **Step 5: Router** — `app/routers/transport.py`, registered in `app/main.py` after `label_option`. Follow `packing_item.py`'s shape: module docstring, `_get` helpers raising 404 with English `detail`, `exclude_unset` PATCH. Positions via a `_next_position(db, column, parent_column, parent_id)`-style helper scoped to the parent (write one small function per parent rather than a generic one if that reads more plainly). Reads use `selectinload(TransportRoute.options).selectinload(TransportOption.departures)`. Duplicate departure: check before insert/update with a `select` on (option_id, day_type, time) excluding self, and raise `HTTPException(409, "That departure already exists for this option.")`; also catch `IntegrityError` on commit, `db.rollback()`, and raise the same 409 (the check is for the message, the constraint is for the race). Every write returns the refreshed row; deletes return 204.

- [ ] **Step 6: Run** `PYTEST tests/ -q` — Expected: PASS.

- [ ] **Step 7: Docs** — `docs/data-model.md`: three new table sections in the existing format, a TOC entry each, and the mermaid shape gains `transport_route → transport_option → transport_departure` (both `ON DELETE CASCADE`). `docs/api.md`: a "Transport" section with the endpoint table above and the 409 rule. Both "Last verified: 2026-09-30".

- [ ] **Step 8: Commit** (`git add` exact paths first)

```bash
git commit -m "feat: transport routes, their options, and departures as rows" -- app/constants.py app/models/__init__.py app/models/transport.py app/schemas/transport.py app/routers/transport.py app/main.py alembic/versions/t1ransport01_transport.py tests/api/test_transport_router.py docs/data-model.md docs/api.md
```

---

### Task 5: Trips and legs, the current trip, and a list's departure source (backend)

**Files:**
- Modify: `app/constants.py`, `app/models/__init__.py`, `app/models/packing_list.py`, `app/schemas/packing_list.py`, `app/services/domain/labels.py`, `app/main.py`, `requirements.txt`
- Create: `app/models/trip.py`, `app/schemas/trip.py`, `app/routers/trip.py`, `app/services/domain/trip.py`, `alembic/versions/t1rip0000001_trips.py`, `tests/api/test_trip_router.py`
- Docs: `docs/data-model.md`, `docs/api.md`, `docs/business-rules.md`

**Interfaces:**
- Consumes: `COLUMN_FOR_KIND` (Task 1), `in_clause`, `TimestampMixin`.
- Produces: `LabelKind.TICKET_TYPE = "ticket_type"`; `TAIPEI` in `app/constants.py` (`ZoneInfo("Asia/Taipei")`); models `Trip`, `TripLeg`; `PackingList.trip_leg`, `PackingList.effective_departure_at`, `PackingList.departure_source`; `current_trip(db, now: datetime) -> Trip | None`; list responses carry `departure_at` (effective) and `departure_source: "list" | "trip_leg"`; leg responses carry `packing_list_name`.

Endpoints:

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/trips` | every trip, legs nested, newest first by latest `departs_at` (leg-less last) |
| GET | `/api/trips/current` | declared **before** `/{trip_id}`; 404 `"No current trip."` when none |
| POST | `/api/trips` | 201 |
| GET / PATCH / DELETE | `/api/trips/{id}` | legs cascade |
| POST | `/api/trips/{trip_id}/legs` | 201 |
| PATCH / DELETE | `/api/trip-legs/{id}` | |

Leg writes: `arrives_at <= departs_at` → 422 (schema `model_validator`; the PATCH path validates the merged values and raises 422 itself); `packing_list_id` naming no list → 404; a list already linked from another leg → 409 `"That packing list is already linked to another leg."`; `ticket_type` is remembered via `remember_label(db, LabelKind.TICKET_TYPE, leg.ticket_type)`.

- [ ] **Step 1: Failing tests** — `tests/api/test_trip_router.py`:

```python
"""Trips: legs, the current-trip rule, and the date a linked list takes."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models import Trip, TripLeg
from app.services.domain.trip import current_trip

TPE = "+08:00"


def leg_payload(departs, arrives, **fields):
    return {"from_place": "彰化火車站", "to_place": "台北車站",
            "departs_at": departs, "arrives_at": arrives, **fields}


@pytest.fixture
def trip(client):
    return client.post("/api/trips", json={"name": "彰化 ⇄ 台北"}).json()


def add_leg(client, trip, departs=f"2026-09-24T18:06:00{TPE}", arrives=f"2026-09-24T20:59:00{TPE}", **fields):
    return client.post(f"/api/trips/{trip['id']}/legs", json=leg_payload(departs, arrives, **fields))


def test_a_leg_reads_back_with_its_booking(client, trip):
    response = add_leg(client, trip, service="火車 - 自強", service_number="5158", seat="5車15號",
                       price=550, ticket_type="電子", booked=True, paid=True, collected=True,
                       booking_code="0589115")
    assert response.status_code == 201
    body = client.get(f"/api/trips/{trip['id']}").json()["legs"][0]
    assert body["booking_code"] == "0589115"  # leading zero survives
    assert (body["booked"], body["paid"], body["collected"]) == (True, True, True)


def test_arriving_before_departing_is_a_422(client, trip):
    bad = add_leg(client, trip, departs=f"2026-09-24T20:00:00{TPE}", arrives=f"2026-09-24T19:00:00{TPE}")
    assert bad.status_code == 422
    assert add_leg(client, trip).status_code == 201  # mirror


def test_a_naive_time_is_a_422(client, trip):
    assert add_leg(client, trip, departs="2026-09-24T18:06:00", arrives="2026-09-24T20:59:00").status_code == 422


def test_a_list_can_be_linked_from_only_one_leg(client, trip):
    lst = client.post("/api/packing-lists", json={"name": "彰化回台北", "saved": True}).json()
    assert add_leg(client, trip, packing_list_id=lst["id"]).status_code == 201
    second = add_leg(client, trip, departs=f"2026-09-28T12:15:00{TPE}",
                     arrives=f"2026-09-28T14:23:00{TPE}", packing_list_id=lst["id"])
    assert second.status_code == 409
    # Mirror: the same leg without the link is fine.
    assert add_leg(client, trip, departs=f"2026-09-28T12:15:00{TPE}",
                   arrives=f"2026-09-28T14:23:00{TPE}").status_code == 201


def test_linking_a_missing_list_is_a_404(client, trip):
    assert add_leg(client, trip, packing_list_id=999999).status_code == 404


def test_a_linked_list_takes_the_taipei_date_of_its_leg(client, trip):
    lst = client.post("/api/packing-lists",
                      json={"name": "l", "saved": True, "departure_at": "2026-01-01"}).json()
    # 00:30 in Taipei is 16:30 the previous day in UTC: this is the case that
    # makes the timezone bite.
    add_leg(client, trip, departs=f"2026-09-24T00:30:00{TPE}", arrives=f"2026-09-24T03:00:00{TPE}",
            packing_list_id=lst["id"])
    body = client.get(f"/api/packing-lists/{lst['id']}").json()
    assert body["departure_at"] == "2026-09-24"
    assert body["departure_source"] == "trip_leg"


def test_an_unlinked_list_keeps_its_own_date(client):
    lst = client.post("/api/packing-lists",
                      json={"name": "l", "saved": True, "departure_at": "2026-01-01"}).json()
    body = client.get(f"/api/packing-lists/{lst['id']}").json()
    assert (body["departure_at"], body["departure_source"]) == ("2026-01-01", "list")


def test_deleting_a_linked_list_keeps_the_leg(client, trip):
    lst = client.post("/api/packing-lists", json={"name": "l", "saved": True}).json()
    leg = add_leg(client, trip, packing_list_id=lst["id"]).json()
    assert client.delete(f"/api/packing-lists/{lst['id']}").status_code == 204
    legs = client.get(f"/api/trips/{trip['id']}").json()["legs"]
    assert [(row["id"], row["packing_list_id"]) for row in legs] == [(leg["id"], None)]


def test_a_legs_ticket_type_is_remembered(client, trip):
    add_leg(client, trip, ticket_type="電子")
    values = [row["value"] for row in client.get("/api/label-options?kind=ticket_type").json()]
    assert values == ["電子"]


# --------------------------------------------------------------------------
# The current trip
# --------------------------------------------------------------------------

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


def make_trip(db, name, *offsets_hours):
    trip = Trip(name=name)
    db.add(trip)
    db.flush()
    for hours in offsets_hours:
        start = NOW + timedelta(hours=hours)
        db.add(TripLeg(trip_id=trip.id, from_place="a", to_place="b",
                       departs_at=start, arrives_at=start + timedelta(hours=1)))
    db.flush()
    return trip


def test_there_is_no_current_trip_without_legs(db_session):
    make_trip(db_session, "empty")
    assert current_trip(db_session, NOW) is None


def test_a_future_trip_beats_a_past_one(db_session):
    make_trip(db_session, "past", -48)
    future = make_trip(db_session, "future", 72)
    assert current_trip(db_session, NOW).id == future.id


def test_the_soonest_future_leg_wins(db_session):
    make_trip(db_session, "later", 72)
    sooner = make_trip(db_session, "sooner", -100, 24)  # has a past leg too
    assert current_trip(db_session, NOW).id == sooner.id


def test_with_nothing_ahead_the_most_recent_past_trip_wins(db_session):
    make_trip(db_session, "older", -200)
    recent = make_trip(db_session, "recent", -300, -10)
    assert current_trip(db_session, NOW).id == recent.id


def test_a_tie_goes_to_the_newer_trip(db_session):
    make_trip(db_session, "first", 24)
    second = make_trip(db_session, "second", 24)
    assert current_trip(db_session, NOW).id == second.id


def test_the_current_endpoint_is_404_when_there_is_none(client):
    assert client.get("/api/trips/current").status_code == 404
```

- [ ] **Step 2: Run** `PYTEST tests/api/test_trip_router.py -q` — Expected: FAIL (imports).

- [ ] **Step 3: Constants, requirements**

`requirements.txt` gains `tzdata==2025.2` with a comment `# zoneinfo's database; Windows has none of its own`. Reinstall: `venv/Scripts/python.exe -m pip install -r requirements-dev.txt`.

`app/constants.py`: `LabelKind.TICKET_TYPE = "ticket_type"`, and

```python
from zoneinfo import ZoneInfo

#: Every leg time is entered and shown here, and a linked list's departure
#: date is the calendar day here — not the server's, not UTC's.
TAIPEI = ZoneInfo("Asia/Taipei")
```

- [ ] **Step 4: Models** — `app/models/trip.py`:

```python
"""A trip and its booked legs."""

from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin


class Trip(Base, TimestampMixin):
    __tablename__ = "trip"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    legs = relationship(
        "TripLeg",
        back_populates="trip",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TripLeg.departs_at",
    )


class TripLeg(Base, TimestampMixin):
    """One booked journey — the sheet's This time row."""

    __tablename__ = "trip_leg"
    __table_args__ = (
        CheckConstraint("arrives_at > departs_at", name="ck_trip_leg_arrives_after_departs"),
        # One leg per list: a list is packed for one journey.
        UniqueConstraint("packing_list_id", name="uq_trip_leg_packing_list_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(
        ForeignKey("trip.id", ondelete="CASCADE", name="fk_trip_leg_trip"),
        nullable=False,
        index=True,
    )
    from_place: Mapped[str] = mapped_column(String, nullable=False)
    to_place: Mapped[str] = mapped_column(String, nullable=False)
    departs_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    arrives_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    service: Mapped[str | None] = mapped_column(String, nullable=True)
    # Text: an identifier, not a quantity.
    service_number: Mapped[str | None] = mapped_column(String, nullable=True)
    seat: Mapped[str | None] = mapped_column(String, nullable=True)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ticket_type: Mapped[str | None] = mapped_column(String, nullable=True)
    # Steps in order, recorded separately: paying without having collected the
    # ticket is a real state.
    booked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    collected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    booking_code: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # SET NULL: deleting the packing list must not delete a booking.
    packing_list_id: Mapped[int | None] = mapped_column(
        ForeignKey("packing_list.id", ondelete="SET NULL", name="fk_trip_leg_packing_list"),
        nullable=True,
    )

    trip = relationship("Trip", back_populates="legs")
    packing_list = relationship("PackingList", back_populates="trip_leg")

    @property
    def packing_list_name(self) -> str | None:
        return self.packing_list.name if self.packing_list else None
```

`app/models/packing_list.py` — `from app.constants import Leg, TAIPEI, Visibility`; replace the "Module 2 prefills it" comment on `departure_at` with "Ignored while a trip leg links this list — see `effective_departure_at`." and add:

```python
    trip_leg = relationship(
        "TripLeg", back_populates="packing_list", uselist=False, passive_deletes=True
    )

    @property
    def effective_departure_at(self) -> date | None:
        """The leg's Taipei calendar day when linked, else the list's own date."""
        if self.trip_leg is not None:
            return self.trip_leg.departs_at.astimezone(TAIPEI).date()
        return self.departure_at

    @property
    def departure_source(self) -> str:
        return "trip_leg" if self.trip_leg is not None else "list"
```

Register `Trip`, `TripLeg` in `app/models/__init__.py`.

- [ ] **Step 5: Migration** — `alembic/versions/t1rip0000001_trips.py`, `revision = "t1rip0000001"`, `down_revision = "t1ransport01"`. Upgrade: create `trip`, create `trip_leg` (columns, `ck_trip_leg_arrives_after_departs`, `fk_trip_leg_trip` CASCADE, `fk_trip_leg_packing_list` SET NULL, `uq_trip_leg_packing_list_id`, index `ix_trip_leg_trip_id`), then widen `ck_label_option_kind` to `('category', 'bag', 'location', 'ticket_type')`. Downgrade: `DELETE FROM label_option WHERE kind = 'ticket_type'`, restore the three-kind constraint, drop index and tables children first. Docstring: why the leg points at the list and not the list at a trip (the earlier `trip_id` intention in `p1acking0001`'s docstring is superseded: a leg is the thing with a departure, so the link lives where the date lives, and a trip-level link could not say which of a pair's two lists belongs to which journey).

- [ ] **Step 6: Label kind** — in `labels.py`, `COLUMN_FOR_KIND[LabelKind.TICKET_TYPE] = TripLeg.ticket_type` (import `TripLeg` from `app.models`).

- [ ] **Step 7: Domain** — `app/services/domain/trip.py`:

```python
"""Which trip is "This time"."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Trip


def current_trip(db: Session, now: datetime) -> Trip | None:
    """The trip with the soonest leg still ahead; failing that, the one whose
    legs ended most recently. Ties go to the newer trip (higher id). A trip
    with no legs is never current.

    Computed in Python over every trip: there are a handful, and the rule reads
    more plainly here than as SQL.
    """
    trips = db.execute(select(Trip).options(selectinload(Trip.legs))).scalars().all()
    ahead = [
        (min(leg.departs_at for leg in trip.legs if leg.departs_at > now), -trip.id, trip)
        for trip in trips
        if any(leg.departs_at > now for leg in trip.legs)
    ]
    if ahead:
        return min(ahead, key=lambda row: row[:2])[2]
    behind = [
        (max(leg.arrives_at for leg in trip.legs), trip.id, trip) for trip in trips if trip.legs
    ]
    if behind:
        return max(behind, key=lambda row: row[:2])[2]
    return None
```

- [ ] **Step 8: Schemas** — `app/schemas/trip.py`: `TripLegBase` (`from_place`, `to_place` `min_length=1`; `departs_at`, `arrives_at` as `pydantic.AwareDatetime`; optional `service`, `service_number`, `seat`, `price` (`ge=0`), `ticket_type`, `booking_code`, `notes`, `packing_list_id`; `booked`/`paid`/`collected` default False) with a `model_validator(mode="after")` raising `ValueError("arrives_at must be after departs_at")`; `TripLegUpdate` all-optional; `TripLegResponse` adds `id`, `trip_id`, `packing_list_name: str | None`. `TripBase{name min_length=1, notes}`, `TripUpdate`, `TripResponse{id, name, notes, legs: list[TripLegResponse]}`.

`app/schemas/packing_list.py` `PackingListFields`:

```python
    #: The EFFECTIVE date: a linked leg's Taipei day, else the list's own.
    departure_at: date | None = Field(validation_alias="effective_departure_at")
    departure_source: Literal["list", "trip_leg"] = "list"
```

(import `Literal`). Ensure the list routers' `selectinload` also loads `PackingList.trip_leg` in `index` and `read` so the summary does not lazy-load per row.

- [ ] **Step 9: Router** — `app/routers/trip.py` per the endpoint table, same shape as the other routers; `current` uses `current_trip(db, datetime.now(timezone.utc))`. Link checks run before the write; also catch `IntegrityError` on commit → rollback → 409 with the same message. PATCH validates merged `departs_at`/`arrives_at` and raises 422 `"arrives_at must be after departs_at"` if violated. Register in `app/main.py`.

- [ ] **Step 10: Run** `PYTEST tests/ -q` — Expected: PASS (incl. the downgrade round trip over all three revisions).

- [ ] **Step 11: Docs** — `docs/data-model.md`: `trip`, `trip_leg` sections; remove "There is no trip table. A list carries its own `departure_at`." and replace with the link rule; `label_option.kind` lists four kinds; mermaid gains `trip → trip_leg` (CASCADE) and `trip_leg -.-> packing_list` (SET NULL, unique). `docs/api.md`: Trips section with the table, 404/409/422 rules, and `departure_source` on list reads. `docs/business-rules.md`: "The current trip" (the rule from the docstring) and "Departure source" (Taipei day, list's own date ignored while linked, unlinked unchanged); fix the "Packing timing" paragraph that says a list carries its own date.

- [ ] **Step 12: Commit** (`git add` exact paths first)

```bash
git commit -m "feat: trips with booked legs, the current trip, and lists dated by their leg" -- requirements.txt app/constants.py app/models/__init__.py app/models/trip.py app/models/packing_list.py app/schemas/trip.py app/schemas/packing_list.py app/routers/trip.py app/routers/packing_list.py app/services/domain/trip.py app/services/domain/labels.py app/main.py alembic/versions/t1rip0000001_trips.py tests/api/test_trip_router.py docs/data-model.md docs/api.md docs/business-rules.md
```

---

### Task 6: The sheet importer

**Files:**
- Modify: `requirements.txt` (`openpyxl==3.1.5`, comment: "scripts/import_sheet.py; in the runtime image so production can be loaded from inside the container")
- Create: `app/services/sheet_import/__init__.py`, `app/services/sheet_import/parse.py`, `app/services/sheet_import/write.py`, `scripts/__init__.py`, `scripts/import_sheet.py`, `tests/sheet_fixture.py`, `tests/unit/test_sheet_parse.py`, `tests/api/test_sheet_import.py`
- Docs: `docs/README.md` status paragraph gains a line, and a new `docs/sheet-import.md` (how to export, run, dry-run, what is skipped). Add it to the `docs/README.md` table.

**Interfaces:**
- Consumes: all models; `Need`, `Status`, `Timing`, `DayType`, `Leg`, `TAIPEI`; `remember_item_labels`, `remember_label`.
- Produces:
  - `parse.py`: `parse_workbook(workbook, trip_start: date, trip_name: str) -> ParsedSheet`, dataclasses `ParsedItem`, `ParsedList`, `ParsedDeparture`, `ParsedOption`, `ParsedRoute`, `ParsedLeg`, `ParsedTrip`, `ParsedSheet(lists, routes, trip, report: list[str])`. Tab names are constants `PACKING_TABS = ("彰化回台北", "台北去彰化")`, `TRANSPORT_TAB = "Transportation"`, `THIS_TIME_TAB = "This time"`.
  - `write.py`: `class ImportClash(Exception)` carrying `clashes: list[str]`; `find_clashes(db, sheet) -> list[str]`; `write_sheet(db, sheet) -> None` (raises `ImportClash` before any write; flushes but does not commit — the caller commits).
  - CLI: `venv/Scripts/python.exe -m scripts.import_sheet <file.xlsx> --trip-start 2026-09-24 [--trip-name "彰化 ⇄ 台北"] [--dry-run]`.

Parsing rules (all from the spec §4; read it):

- **Packing tabs:** locate columns by header text in row 1 (`類別`, `項目`, `數量`, `已打包數量`, `打包狀態`, `Double Check`, `打包時機`, `需求`, `取得地點`, `備註`); the detail column is the one immediately right of `項目`. Blank `類別` or `項目` inherits the value above. A row whose `項目` is `無` is skipped and reported (`"<tab> row <n>: 無 under <category> skipped"`). A row with every cell blank is ignored silently. Mappings: status 未打包/已打包/不需打包; Double Check 不需確認→(F,F), 未確認→(T,F), 確認→(T,T); timing 隨時/出發前晚/出發當天/出發前; need 需要/需帶/需買/blank→None; numbers via `as_int` (float 1.0 → 1, blank → None); `已打包數量` blank → 0. An unknown vocabulary value raises `ValueError` naming tab, row and value — never guessed.
- **Lists:** name = tab name; `saved=True`; `leg`: name containing `去` → `outbound`, `回` → `return`; both lists share `pair_id = "sheet-" + "-".join(sorted(PACKING_TABS))`; positions 0..n in row order.
- **Transportation:** headers by text. Rows grouped into routes by (`目標起點`, `目標終點`) in first-seen order. A row with a start and no end is skipped and reported. A row with no `交通工具` contributes a route (and its `時間` becomes the route note `"時間 <value>"` if present) but no option. `提前買票`: 需要 → True, else False. Departure cells: `P..S` weekday, `T..W` holiday (locate by header text `平日班次 (早)` etc.). A cell may be a `datetime.time`, a `datetime.datetime`, a float day fraction (`round(value * 1440)` minutes), or a string of comma-separated tokens each optionally prefixed `*`. `...` → no departures and the option note gains `"<平日|假日> <早|中|下午|晚> 班次未知"`, reported. After parsing, each time is checked against its column's bucket (same boundaries as `departures.js`: 12:00/14:00/18:00); a mismatch is reported (`"6933A 假日 中: 11:35 is before 12:00"`) and the time is still imported.
- **This time:** `時間` like `Thu 18:06-20:59`. The first leg's weekday must equal `trip_start`'s weekday (else `ValueError`); each later leg takes the next date on or after the previous leg's date with its weekday. Times are Asia/Taipei. `車號`, `訂票代碼` → `as_text` (float 5158.0 → "5158"). `訂票狀態` split on `,`, trimmed: `已訂票`→booked, `付款`→paid, `取票`→collected; anything else → `ValueError`. Link a leg to the parsed list whose name, split on its `去`/`回`, gives `(a, b)` with `from_place.startswith(a)` and `to_place.startswith(b)`; no match → unlinked and reported.

Clashes (`find_clashes`): a packing list with the same name; a route with the same (`from_place`, `to_place`); a trip with the same name. Each is one message line.

- [ ] **Step 1: Failing unit tests** — the in-memory workbook lives in `tests/sheet_fixture.py` (shared by the unit and the writer tests); `tests/unit/test_sheet_parse.py` imports `workbook` from it and asserts field by field. `tests/sheet_fixture.py` holds the three header constants and `workbook()` below; the test file holds the `sheet` fixture and the cases, and imports `from app.constants import TAIPEI`:

```python
from datetime import date, datetime, time

import openpyxl
import pytest

from app.services.sheet_import.parse import parse_workbook

PACK_HEADER = ["類別", "項目", None, "數量", "已打包數量", "打包狀態", "Double Check",
               "打包時機", "需求", "取得地點", "備註"]
TRANSPORT_HEADER = ["目標起點", "目標終點", "交通工具", "提前買票", "路線圖", "時刻表", "即時動態",
                    "方向", "起點", "終點", "實際起點", "實際終點", "價錢", "時間", "班次間隔",
                    "平日班次 (早)", "平日班次 (中)", "平日班次 (下午)", "平日班次 (晚)",
                    "假日班次 (早)", "假日班次 (中)", "假日班次 (下午)", "假日班次 (晚)"]
THIS_TIME_HEADER = ["出發地點", "目的地", "時間", "時長", "車種", "車號", "座位", "價錢",
                    "車票類型", "訂票狀態", "訂票代碼", "備註"]


def workbook():
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    back = wb.create_sheet("彰化回台北")
    back.append(PACK_HEADER)
    back.append(["重要", "錢包", None, None, None, "未打包", "未確認", "出發前", "需帶", "彰化", None])
    back.append([None, "鑰匙", "家鑰匙", None, None, "已打包", "確認", "隨時", "需帶", "彰化", None])
    back.append([None, None, "宿舍鑰匙", 1.0, None, "不需打包", "不需確認", "出發前晚", None, "彰化", "8/14沒帶"])
    back.append(["書 / 文具", "無"])
    there = wb.create_sheet("台北去彰化")
    there.append(PACK_HEADER)
    there.append(["食物", "水果", None, 2.0, 1.0, "未打包", "不需確認", "出發當天", "需買", "新北", None])
    wb.create_sheet("Ignored tab").append(["anything"])
    transport = wb.create_sheet("Transportation")
    transport.append(TRANSPORT_HEADER)
    row = ["彰化火車站", "宿舍", "彰化客運6933A", "不需要", "http://map", "http://tt", None,
           "往鹿港乘車處", "高鐵台中", "鹿港", "彰化", "南瑤宮", 22.0, "7m", None,
           None, None, None, None,
           "7:30, *9:15", time(11, 35), "*14:15", 0.7777777777777778]
    transport.append(row)
    transport.append(["彰化火車站", "宿舍", "彰化客運6912"] + [None] * 16 + ["...", "...", None, None])
    transport.append(["宿舍", "彰化火車站"])
    transport.append(["新烏日火車站"])
    transport.append(["彰化火車站", "台北車站"] + [None] * 11 + ["2h-2h30m"])
    this_time = wb.create_sheet("This time")
    this_time.append(THIS_TIME_HEADER)
    this_time.append(["彰化火車站", "台北車站", "Thu 18:06-20:59", "2h53m", "火車 - 自強", 5158.0,
                      "5車15號", 550.0, "電子", "已訂票, 付款, 取票", 5891150.0, "提前買晚餐車上吃"])
    this_time.append(["台北車站", "彰化火車站", "Mon 12:15-14:23", "2h08m", "火車 - 自強 (3000)", 137.0,
                      "3車31號", 550.0, "電子", "已訂票, 付款", 5891246.0, "不吃午餐"])
    return wb


@pytest.fixture
def sheet():
    return parse_workbook(workbook(), trip_start=date(2026, 9, 24), trip_name="彰化 ⇄ 台北")
```

Tests (each a function; write the asserts exactly):

- `test_blank_category_and_name_inherit_from_the_row_above`: list `彰化回台北` items → `[(i.category, i.name, i.detail) ...] == [("重要","錢包",None), ("重要","鑰匙","家鑰匙"), ("重要","鑰匙","宿舍鑰匙")]`.
- `test_the_sheet_vocabulary_maps_onto_stored_values`: item 0 `status="not_packed", needs_double_check=True, double_checked=False, timing="just_before", need="bring", location="彰化"`; item 1 `status="packed", (True, True), timing="whenever"`; item 2 `status="no_need", (False, False), timing="night_before", need=None, quantity=1, quantity_packed=0, notes="8/14沒帶"`.
- `test_an_item_named_無_is_skipped_and_reported`: no item named `無`; some report line contains `無`.
- `test_lists_are_a_saved_round_trip_pair`: `彰化回台北` leg `return`, `台北去彰化` leg `outbound`, both `saved`, equal non-null `pair_id`.
- `test_other_tabs_are_ignored`: parse succeeds with `Ignored tab` present and nothing mentions it.
- `test_routes_group_rows_by_their_two_places`: routes `[(r.from_place, r.to_place) ...] == [("彰化火車站","宿舍"), ("宿舍","彰化火車站"), ("彰化火車站","台北車站")]`; first route has two options `["彰化客運6933A","彰化客運6912"]`; `宿舍→彰化火車站` has none; `彰化火車站→台北車站` has none and `notes == "時間 2h-2h30m"`.
- `test_departures_read_strings_stars_times_and_day_fractions`: 6933A departures `[(d.day_type, d.time, d.irregular) ...] == [("holiday", time(7,30), False), ("holiday", time(9,15), True), ("holiday", time(11,35), False), ("holiday", time(14,15), True), ("holiday", time(18,40), False)]`.
- `test_a_time_in_the_wrong_column_is_imported_and_reported`: 11:35 is present (above) and a report line contains `11:35`.
- `test_three_dots_means_unknown`: 6912 has no departures; its `notes` contains `假日 早 班次未知` and `假日 中 班次未知`.
- `test_a_row_without_a_destination_is_skipped_and_reported`: a report line contains `新烏日火車站`.
- `test_option_fields_are_typed`: 6933A `price == 22`, `advance_ticket is False`, `board_at == "彰化"`, `alight_at == "南瑤宮"`, `line_from == "高鐵台中"`, `duration == "7m"`, `route_map_url == "http://map"`.
- `test_legs_get_dates_from_the_trip_start_in_taipei`: leg 0 `departs_at == datetime(2026,9,24,18,6,tzinfo=TAIPEI)`, `arrives_at` 20:59 same day; leg 1 `departs_at == datetime(2026,9,28,12,15,tzinfo=TAIPEI)`.
- `test_leg_identifiers_stay_text`: leg 0 `service_number == "5158"`, `booking_code == "5891150"`, `price == 550`.
- `test_booking_status_is_three_flags`: leg 0 `(booked, paid, collected) == (True, True, True)`; leg 1 `== (True, True, False)`.
- `test_legs_link_to_the_list_for_their_journey`: leg 0 `packing_list_name == "彰化回台北"`, leg 1 `== "台北去彰化"`.
- `test_a_trip_start_on_the_wrong_weekday_is_refused`: `parse_workbook(workbook(), trip_start=date(2026,9,25), ...)` raises `ValueError`.
- `test_an_unknown_status_is_refused_not_guessed`: set `wb["彰化回台北"]["F2"] = "半打包"` then parse → `ValueError` whose message contains `半打包`.

- [ ] **Step 2: Run** `PYTEST tests/unit/test_sheet_parse.py -q` — Expected: FAIL (module missing). (`pip install openpyxl==3.1.5` first, after adding it to `requirements.txt`.)

- [ ] **Step 3: Implement `parse.py`** to make every case pass. Keep it as small, single-purpose functions: `_header_index(row) -> dict[str, int]`, `as_int(value)`, `as_text(value)`, `_parse_time_cell(value) -> list[tuple[time, bool]] | None` (None for `...`), `_bucket(t) -> str`, `_parse_packing(ws) -> ParsedList`, `_parse_transport(ws) -> list[ParsedRoute]`, `_parse_this_time(ws, trip_start, trip_name, lists) -> ParsedTrip`, each appending to a shared `report` list. Dataclasses mirror the model columns by name, plus `ParsedLeg.packing_list_name`. Read `ws.iter_rows(min_row=2, values_only=True)`; row numbers in messages are sheet row numbers (header is row 1).

- [ ] **Step 4: Run** — Expected: PASS.

- [ ] **Step 5: Failing writer tests** — `tests/api/test_sheet_import.py`:

```python
from datetime import date

import pytest

from app.models import PackingList, TransportRoute, Trip
from app.services.sheet_import.parse import parse_workbook
from app.services.sheet_import.write import ImportClash, write_sheet
from tests.sheet_fixture import workbook


@pytest.fixture
def sheet():
    return parse_workbook(workbook(), trip_start=date(2026, 9, 24), trip_name="彰化 ⇄ 台北")


def test_an_import_writes_lists_routes_and_the_trip(db_session, sheet):
    write_sheet(db_session, sheet)
    db_session.commit()
    names = sorted(row.name for row in db_session.query(PackingList))
    assert names == ["台北去彰化", "彰化回台北"]
    assert db_session.query(TransportRoute).count() == 3
    trip = db_session.query(Trip).one()
    assert [leg.packing_list.name for leg in trip.legs] == ["彰化回台北", "台北去彰化"]


def test_an_import_remembers_labels(client, db_session, sheet):
    write_sheet(db_session, sheet)
    db_session.commit()
    kinds = {row["kind"] for row in client.get("/api/label-options").json()}
    assert {"category", "location", "ticket_type"} <= kinds


def test_an_import_refuses_when_any_target_exists_and_writes_nothing(db_session, sheet):
    # Load-bearing: one pre-existing route is the only clash, so the refusal
    # has to come from the route check and not from an empty table.
    db_session.add(TransportRoute(from_place="宿舍", to_place="彰化火車站"))
    db_session.commit()
    with pytest.raises(ImportClash) as refused:
        write_sheet(db_session, sheet)
    assert any("宿舍" in line for line in refused.value.clashes)
    assert db_session.query(PackingList).count() == 0
    assert db_session.query(Trip).count() == 0


def test_an_import_into_an_empty_database_has_no_clashes(db_session, sheet):
    from app.services.sheet_import.write import find_clashes

    assert find_clashes(db_session, sheet) == []
```

- [ ] **Step 6: Implement `write.py`** — `find_clashes` then, if any, `raise ImportClash(clashes)` before touching anything; otherwise add lists and items (calling `remember_item_labels` per item), routes/options/departures (positions in parsed order), the trip and legs (resolving `packing_list_name` to the created list; `remember_label(db, LabelKind.TICKET_TYPE, ...)`), `db.flush()`. Never commits.

- [ ] **Step 7: CLI** — `scripts/import_sheet.py`:

```python
"""Load the owner's travel sheet into this app's database.

    venv/Scripts/python.exe -m scripts.import_sheet export.xlsx --trip-start 2026-09-24 --dry-run

Reads only the four tabs named in app/services/sheet_import/parse.py. The
export carries booking codes: keep it out of the repository. See
docs/sheet-import.md.
"""

import argparse
import sys
from datetime import date

import openpyxl

from app.database import SessionLocal
from app.services.sheet_import.parse import parse_workbook
from app.services.sheet_import.write import ImportClash, write_sheet


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path")
    parser.add_argument("--trip-start", type=date.fromisoformat, required=True)
    parser.add_argument("--trip-name", default="彰化 ⇄ 台北")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    sheet = parse_workbook(
        openpyxl.load_workbook(args.path), trip_start=args.trip_start, trip_name=args.trip_name
    )
    print(f"{len(sheet.lists)} lists, {sum(len(l.items) for l in sheet.lists)} items, "
          f"{len(sheet.routes)} routes, {len(sheet.trip.legs)} legs")
    for line in sheet.report:
        print(f"  note: {line}")

    with SessionLocal() as db:
        try:
            write_sheet(db, sheet)
        except ImportClash as clash:
            for line in clash.clashes:
                print(f"  refused: {line}", file=sys.stderr)
            return 1
        if args.dry_run:
            db.rollback()
            print("dry run: nothing written")
        else:
            db.commit()
            print("imported")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Create empty `scripts/__init__.py` and `app/services/sheet_import/__init__.py` (one-line docstring each).

- [ ] **Step 8: Run** `PYTEST tests/ -q` and `venv/Scripts/ruff check .` — Expected: PASS/clean.

- [ ] **Step 9: Docs** — `docs/sheet-import.md` (present tense): what the four tabs map to (link to data-model), how to export (`File → Download → .xlsx`, or `https://docs.google.com/spreadsheets/d/<id>/export?format=xlsx`), the command, `--dry-run`, the refusal, the quirk table from spec §4, "the export is never committed", and "production is loaded from inside the container on the box by the manager session". Add the page to `docs/README.md`'s table.

- [ ] **Step 10: Commit** (`git add` exact paths first)

```bash
git commit -m "feat: import the travel sheet's four tabs" -- requirements.txt app/services/sheet_import/__init__.py app/services/sheet_import/parse.py app/services/sheet_import/write.py scripts/__init__.py scripts/import_sheet.py tests/sheet_fixture.py tests/unit/test_sheet_parse.py tests/api/test_sheet_import.py docs/sheet-import.md docs/README.md
```

---

### Task 7: The packing sheet UI per the owner's review, in Traditional Chinese

**Files:**
- Create: `frontend/src/components/RowMenu.jsx`, `frontend/src/components/ConfirmDialog.jsx`, `frontend/src/hooks/useLongPress.js`
- Modify: `frontend/src/components/Grid.jsx`, `frontend/src/components/Checklist.jsx`, `frontend/src/components/Cell.jsx`, `frontend/src/components/EvictDialog.jsx`, `frontend/src/components/States.jsx`, `frontend/src/pages/PackingList.jsx`, `frontend/src/pages/PackingLists.jsx`, `frontend/src/pages/Options.jsx`, `frontend/src/App.jsx`, `frontend/src/api/endpoints.js`, `frontend/index.html` (`lang="zh-Hant-TW"`)
- Docs: `docs/frontend.md`

**Interfaces:**
- Consumes: Task 3's `lib/*`; Task 1/2 API (`detail`, `need`, `location`, `after_id`, `/reset`); Task 5's `departure_source`.
- Produces: `endpoints.packingLists.reset(id)`; `RowMenu({ open, onClose, actions: [{label, onSelect, danger?}] })`; `ConfirmDialog({ title, body, confirmLabel, onConfirm, onCancel })`; `useLongPress(onLongPress, { ms = 500 }) -> { handlers, consumeClick() }`.

Requirements (spec §1a — each bullet is checked in review):

1. **Grid columns, in order:** 類別 · 項目 (header spans two cells: name, detail) · 數量 (quantity + unit, one cell) · 已打包數量 (its own number cell) · 打包狀態 · Double Check · 打包時機 · 需求 · 取得地點 · 備註 · ⋯. `bag` is not shown (it stays in the data; the sheet has no such column — say so in `docs/frontend.md`).
2. **Grouping:** when `sort` is null, rows come from `groupRuns(items)`; a row with `showCategory=false` renders an empty 類別 cell (still clickable to edit — the click opens the editor with the inherited value pre-filled), `showName=false` likewise for 項目. Draw the row's top border lighter (`border-border/40`) when it continues a name run, so a group reads as one block. Under any other sort every cell shows its value.
3. **打包狀態 cell:** shows `STATUS_LABELS[status]` as a compact pill (`已打包` brand-coloured, `未打包` muted, `不需打包` faint + line-through). **Click** → `onPatch(id, { status: tapStatus(status) })`. **Long-press** (500 ms, via `useLongPress`) or the row's ⋯ → opens `RowMenu`. A long-press must not also fire the click (`consumeClick`).
4. **Double Check cell:** `SelectCell` over `CHECK_STATES` with `CHECK_LABELS`, writing `CHECK_FIELDS[state]`.
5. **需求 cell:** `SelectCell` over `['', ...NEEDS]` with `{ '': '—', ...NEED_LABELS }`, writing `null` for `''`. Extend `SelectCell` to accept that (it currently assumes a value in `options`).
6. **取得地點 cell:** `TextCell` with `values('location')` suggestions, `listId="location-options"`.
7. **Row ⋯ menu (`RowMenu`)**, same actions in both views: `設為不需打包` (or `改回未打包` when already no_need) · `新增變化` → `POST items {name: item.name, category: item.category, after_id: item.id}` · in the checklist only, the three Double Check states · `刪除` (danger; the sheet's ✕ column moves into this menu).
8. **Adding a row** in the sheet: placeholder `▸ 新增一列…`; in the checklist `⊕ 新增項目`.
9. **Checklist:** groups via `groupForChecklist`; a group of one renders as today's single line (`name`, with ` · detail` if any); a group of several renders the name as a heading line and each variant indented beneath with its own tick. The tick uses `tapStatus`; long-press on the tick opens `RowMenu`. The quiet second line is `[NEED_LABELS[need], location, quantity text, notes].filter(Boolean).join(' · ')`, quantity text `已打包 {packed} / {quantity}{unit}`; the outstanding-check link reads `待確認`. Done fold: `已完成 ({n})`. Empty: `清單還是空的，從下面新增第一項。` / `全部都處理好了。`
10. **重設狀態:** a button in the list header; opens `ConfirmDialog` (`title="重設狀態？"`, body `所有已打包的項目會改回未打包，已打包數量歸零，Double Check 改回未確認。不需打包的項目不變。`, confirm `重設`). Confirm → `POST endpoints.packingLists.reset(id)`, invalidating the list and index keys.
11. **Header text:** view switch `表格` / `清單`; back link `← 所有清單`; `leaving()` → `未設定日期`, `今天出發 · {d}`, `明天出發 · {d}`, `{n} 天後出發 · {d}`, `已出發 {n} 天 · {d}`; when `departure_source === 'trip_leg'` append ` · 由 This time 行程設定` and do not offer a date editor. Progress → `已處理 {s} / {n}`, ` · {u} 項待確認`, ` · 可以出發了`.
12. **Everything else zh-TW:** `States.jsx` defaults `載入中…`, `發生錯誤。`, `再試一次`; `EvictDialog` title `這會刪除一份清單`, and it renders its own body `已有 3 份進行中的清單。建立新的清單會刪除最舊的：` followed by the names — not the API `detail`; its buttons (read the file) translated (`改為保存它`, `刪除並建立`, `取消`). `PackingLists.jsx` and `Options.jsx`: every visible string translated (read both files end to end; grep for `>[A-Z]`, `placeholder="`, `aria-label="`, `title=` afterwards to catch stragglers); leg shown via `LEG_LABELS`; option kinds via `LABEL_KIND_LABELS`, and `Options` lists all four kinds. Nav: `travel` · `打包清單` · `Transportation` · `This time` · `選項` (the last three link to `/transport`, `/trip`, `/options`; add the routes in Task 8/9, but add the nav links here pointing at them — until then they fall through to the index, which is acceptable for one task).
13. `aria-label`s are zh-TW too (e.g. `` `${item.name}：${STATUS_LABELS[item.status]}，點一下切換` ``).

`useLongPress`:

```js
import { useRef } from 'react'

/**
 * Long-press without a library: pointer down starts a timer, up or leave
 * cancels it. `consumeClick()` tells the click handler that fires after a
 * long-press to do nothing, so one gesture never does both things.
 */
export function useLongPress(onLongPress, { ms = 500 } = {}) {
  const timer = useRef(null)
  const fired = useRef(false)

  const start = (event) => {
    fired.current = false
    timer.current = setTimeout(() => {
      fired.current = true
      onLongPress(event)
    }, ms)
  }
  const cancel = () => clearTimeout(timer.current)

  return {
    handlers: {
      onPointerDown: start,
      onPointerUp: cancel,
      onPointerLeave: cancel,
      onContextMenu: (event) => event.preventDefault(),
    },
    consumeClick: () => {
      const was = fired.current
      fired.current = false
      return was
    },
  }
}
```

(Use it as `onClick={() => { if (press.consumeClick()) return; toggle() }}`.)

`RowMenu` is a small popover (`role="menu"`, buttons `role="menuitem"`, closes on outside click and Escape) anchored to the row; on phone widths it renders as a bottom sheet like `EvictDialog`. `ConfirmDialog` copies `EvictDialog`'s markup and primary/secondary styling with generic props.

- [ ] **Step 1:** Implement items 1–13. Keep `Grid.jsx` readable: extract `StatusCell` and a `GroupedRow` (or equivalent) into `Grid.jsx`-local components rather than growing one render function.
- [ ] **Step 2:** `cd frontend && npm run lint && npm test && npm run build` — Expected: clean.
- [ ] **Step 3: Look at it.** Start the app (`venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8002` and `cd frontend && npm run dev -- --port 5175 --strictPort`, or reuse running ones), open `http://localhost:5175`, create a saved list and verify by hand: column order; a variant added via ⋯ lands directly under its row and the name cell is blank; sorting by 打包時機 shows every name and unsorting regroups; tap toggles 未打包⇄已打包; long-press opens the menu and does not also toggle; 不需打包 row is struck and one tap returns it to 未打包; 重設狀態 leaves a 不需打包 row alone; checklist groups variants; no English left on screen except Double Check / Transportation / This time / travel. Use the claude-in-chrome tools if available; otherwise report that the check was not done.
- [ ] **Step 4: Docs** — `docs/frontend.md`: the zh-TW rule and `lib/labels.js` as its single home; the column order; grouping; three-stored-two-tapped status and the long-press/⋯ route; 重設狀態; that `bag` is not shown.
- [ ] **Step 5: Commit** — `feat: the packing sheet in the sheet's own words, with variants, tap status and reset` with the exact list of files touched.

---

### Task 8: The Transportation page

**Files:**
- Create: `frontend/src/pages/Transport.jsx`
- Modify: `frontend/src/App.jsx` (route `/transport`), `frontend/src/api/endpoints.js`
- Docs: `docs/frontend.md`

**Interfaces:**
- Consumes: Task 4 endpoints; `lib/departures.js`, `lib/labels.js` (`DAY_TYPE_LABELS`, `BUCKET_LABELS`), `TextCell`, `useApiQuery`, `useApiMutation`, `send`, `States`.
- Produces: `endpoints.transport = { routes: () => '/api/transport-routes', route: (id) => ..., options: (routeId) => `/api/transport-routes/${routeId}/options`, option: (id) => `/api/transport-options/${id}`, departures: (optionId) => `/api/transport-options/${optionId}/departures`, departure: (id) => `/api/transport-departures/${id}` }`.

Requirements:

1. Page title `Transportation`. Query key `['transport-routes']`; every mutation invalidates it.
2. Routes as sections: heading `{from_place} → {to_place}` (both `TextCell`s), `notes` as a `TextCell` beneath (placeholder `備註`), a ⋯ with `刪除路線` behind `ConfirmDialog`.
3. Each option a card: `mode` as the card title (`TextCell`); a two-column definition grid of 方向, 起點 → 終點 (`line_from`/`line_to`), 實際起點 → 實際終點 (`board_at`/`alight_at`), 價錢 (number, shown `NT$22`), 時間 (`duration`), 班次間隔 (`headway`), 提前買票 (a toggle showing 需要/不需要), 備註 — each field editable in place with the sheet rules (Enter/blur commits, Escape reverts, no save button). Links row: 路線圖 / 時刻表 / 即時動態 as links opening in a new tab when set, each with a small ✎ to edit the URL.
4. Departures: two rows, 平日 and 假日; each row shows the four buckets `早 / 中 / 下午 / 晚` via `groupByBucket`, each time a chip `formatDeparture(d)`; irregular chips dashed-outlined with `title="不一定有這班"`. The chip equal to `nextDeparture(option.departures, now)` is highlighted (brand fill) with `下一班` beside it; `now` from a `useState(new Date())` refreshed every 60 s by an interval, cleared on unmount. Each chip has ✕ (delete). At the end of each day-type row an input (`placeholder="加一班，例如 *13:40"`) parsed with `parseDepartureInput`; invalid input shows `時間格式不對` under it and sends nothing; a 409 shows `這班已經有了`.
5. `+ 新增交通方式` on each route (mode input, Enter creates); `+ 新增路線` at the page bottom (from/to inputs).
6. Empty state: `還沒有路線。` with the add-route form.
7. Mobile first: cards stack full width under 720 px; buckets wrap; no horizontal page scroll.

- [ ] **Step 1:** Implement. - [ ] **Step 2:** `npm run lint && npm test && npm run build`. - [ ] **Step 3:** Look at it in the browser against a route created by hand (add a route, an option, a `*13:40` holiday departure, check the bucket and the marker, add a duplicate and see `這班已經有了`). - [ ] **Step 4:** `docs/frontend.md` section "Transportation". - [ ] **Step 5:** Commit `feat: the Transportation page` with exact paths.

---

### Task 9: The This time page

**Files:**
- Create: `frontend/src/pages/Trip.jsx`
- Modify: `frontend/src/App.jsx` (routes `/trip` and `/trips/:tripId`), `frontend/src/api/endpoints.js`
- Docs: `docs/frontend.md`

**Interfaces:**
- Consumes: Task 5 endpoints; `lib/trips.js`, `BOOKING_LABELS`, `TextCell`, `ConfirmDialog`, packing-list index endpoint for the link picker.
- Produces: `endpoints.trips = { index: () => '/api/trips', current: () => '/api/trips/current', detail: (id) => ..., legs: (tripId) => `/api/trips/${tripId}/legs`, leg: (id) => `/api/trip-legs/${id}` }`.

Requirements:

1. `/trip` loads `/api/trips/current`; a 404 (check `error.status === 404`) is the empty state `還沒有行程。` with a create form (trip name). `/trips/:tripId` shows that trip with the same component.
2. Header: trip name (`TextCell`), notes, ⋯ `刪除行程` behind `ConfirmDialog`.
3. Legs as cards in `departs_at` order. Each card:
   - Top line large: `{from_place} → {to_place}`; beneath `formatTaipei(departs_at)` – arrival time (`HH:mm` only when same Taipei day) and `formatDuration(...)`.
   - 車種 · 車號 · 座位 · 價錢 (`NT$550`) · 車票類型 (suggested from `values('ticket_type')`) as editable fields.
   - 訂票代碼 in a large monospace box; tapping it copies via `navigator.clipboard.writeText` and shows `已複製` for 2 s (wrap in try/catch; on failure show `無法複製`). A small ✎ edits it.
   - Three ticks `已訂票`, `付款`, `取票`, each toggling its own field.
   - 備註 editable.
   - Packing list: when linked, a link `打包清單：{packing_list_name}` to `/lists/{id}`; a ✎ opens a `<select>` of all lists (from the index: `recent`, `saved`, `templates`, deduplicated by id) plus `（不連結）`; a 409 shows `這份清單已經連到別的行程段`.
   - Editing times: ✎ opens two `datetime-local` inputs prefilled with `taipeiInputValue`, saved with `fromTaipeiInput`; a 422 shows `抵達時間要晚於出發時間`.
   - ⋯ `刪除這段` behind `ConfirmDialog`.
4. `+ 新增一段` form: from, to, two datetime-local inputs (Taipei), creates the leg.
5. Below the current trip: `過去的行程` — every other trip from `/api/trips`, each a link `/trips/{id}` with its name and date range. Omit the heading when there are none.
6. A list linked here shows its date as set by the trip (Task 7 item 11) — verify both screens agree.

- [ ] **Step 1:** Implement. - [ ] **Step 2:** `npm run lint && npm test && npm run build`. - [ ] **Step 3:** Look at it: create a trip, two legs, link a list, confirm the list's header date follows the leg and says `由 This time 行程設定`; copy a booking code. - [ ] **Step 4:** `docs/frontend.md` section "This time". - [ ] **Step 5:** Commit `feat: the This time page` with exact paths.

---

### Task 10: Import the sheet locally, close out the docs, and verify the branch

**Files:**
- Modify: `docs/notes/decisions.md`, `docs/README.md`
- Delete: `docs/superpowers/specs/2026-09-30-sheet-parity-design.md`, `docs/superpowers/plans/2026-09-30-sheet-parity.md`

- [ ] **Step 1: Migrate the local database** — `venv/Scripts/python.exe -m alembic upgrade head`, then confirm `docker exec cg1618-dev-db psql -U postgres -d travel -tAc "SELECT version_num FROM alembic_version"` prints `t1rip0000001`.
- [ ] **Step 2: Remove the preview list** — `DELETE /api/packing-lists/<id>` for the list named `Preview (delete me) — 台北去彰化` (look up its id from `GET /api/packing-lists`; it is the only list whose name starts with `Preview`). Delete nothing else.
- [ ] **Step 3: Export and dry-run** — download `https://docs.google.com/spreadsheets/d/1FM21nRj0h2PqG2Y4Naqxz3JIm8JYwKksHgnNmZBzB8s/export?format=xlsx` into the session scratchpad (never the repository), then `venv/Scripts/python.exe -m scripts.import_sheet <scratch>/travel.xlsx --trip-start 2026-09-24 --dry-run`. Expected: 2 lists, 85 items (彰化回台北 42 rows; 台北去彰化 45 rows minus its two `無` rows = 43 — recount from the output rather than trusting this figure, and report the actual number), the routes, 2 legs, and notes for: the two `無` rows, the `新烏日火車站` row, 6912's unknown cells, and 6933A's `11:35` sitting in the 中 column.
- [ ] **Step 4: Import** — the same command without `--dry-run`. Expected `imported`. Run it a second time and confirm it refuses with every clash named.
- [ ] **Step 5: Record decisions** — append to `docs/notes/decisions.md`, one short section each, as it ended up: item + detail over parent/child items and over folding into the name; `need` closed vs `location` open; departures as rows, not four text columns; the leg links the list (over a trip owning the pair and over `packing_list.trip_id`, superseding the first packing revision's intention); status stored as three and tapped as two; reset leaves `no_need` alone; the UI in the sheet's own words with stored values in English; the importer shipping in the runtime image; `bag` retained but not shown.
- [ ] **Step 6: README** — `docs/README.md` status paragraph: packing lists, transport and trips are built, the sheet is importable; still no buying list and no rules. Table rows for any page added.
- [ ] **Step 7: Delete the spec and this plan.**
- [ ] **Step 8: Full verification** — `PYTEST tests/ -q`, `venv/Scripts/ruff check .`, `cd frontend && npm run lint && npm test && npm run build`, `venv/Scripts/python.exe -m alembic heads` (exactly one: `t1rip0000001`). All green; report the counts.
- [ ] **Step 9: Commit** `docs: record the sheet-parity decisions and retire the spec and plan` — exact paths including the two deletions (`git rm` them).
- [ ] **Step 10: Push** `git push`. Opening the PR into `dev` is done by the main session, not by a subagent.

---

## Outstanding: final review fix wave

Tasks 1-10 are complete and reviewed (HEAD 9ed108d; the local `travel` database holds the imported sheet at revision `t1rip0000001`). The whole-branch review returned "ready with fixes". Fix all of the following in one pass, re-review that diff, then open the PR into `dev`.

Branch feat/sheet-parity, HEAD 9ed108d. Spec: docs/superpowers/specs/2026-09-30-sheet-parity-design.md.

## Important

1. **No way to create a second trip from the UI.** `frontend/src/pages/Trip.jsx` shows `CreateTrip` only when `/api/trips/current` is 404; once any trip exists (the imported 彰化 ⇄ 台北 stays current), no page offers a new trip. Add a `+ 新增行程` control on the trip view (header or beside the other-trips list) that creates a trip and navigates to `/trips/{id}`. Document it in `docs/frontend.md`.

2. **Trip has no `visibility` column.** travel/CLAUDE.md: "Shareable entities carry a visibility field from the first migration", and a single trip's information is named as the thing to be shared. Ruling: add a NEW Alembic revision `t2rip0000002` (down_revision `t1rip0000001`) that adds `trip.visibility` text NOT NULL server_default 'private' with `ck_trip_visibility` built from the `Visibility` enum (same shape as `ck_packing_list_visibility`); downgrade drops both. Model: `app/models/trip.py` mirrors `PackingList.visibility` (reuse `in_clause`, `Visibility`). Do NOT expose it in the API/UI (nothing reads it yet, same as packing_list). Docs: data-model.md trip table + constraint row. Test: a model-level test that an invalid visibility is refused by the constraint and the default is 'private'. Then apply it to the LOCAL `travel` database: `venv/Scripts/python.exe -m alembic upgrade head` (the imported data must survive — verify the counts after: 2 lists, 85 items, 4 routes, 5 options, 38 departures, 1 trip, 2 legs).

3. **Explicit null on required packing fields is still a 500.** `app/schemas/packing_item.py` `PackingItemUpdate` and `app/schemas/packing_list.py` `PackingListUpdate` must subclass `NonNullableUpdate` (`app/schemas/base.py`) listing their NOT NULL fields (read the models: e.g. item name, quantity_packed, status, timing, needs_double_check, double_checked, position; list name, saved, template — check each against the model, and remember `evict_confirmed` is not a column). Tests: `{"name": null}` on an item → 422, `{"status": null}` → 422, mirror `{"notes": null}` → 200; list `{"saved": null}` → 422, mirror `{"departure_at": null}` → 200. Also add the two tests the review asked for: PATCH clearing `need` and `location` to null → 200 and reads back null; a leg PATCH that sets `ticket_type` remembers it as a label option. Extend the api.md note on the null rule to cover packing.

4. **App CLAUDE.md status is stale.** `travel/CLAUDE.md` lines ~25-31 say packing is the only built module and there is no trip or transport. Rewrite that paragraph to match `docs/README.md`'s status (packing lists, transport and trips built; the sheet is importable; no buying list and no rules yet). Change nothing else in CLAUDE.md.

5. **Stale doc claims** — fix each, and grep each claim across docs/ and CLAUDE.md for second copies:
   - `docs/notes/decisions.md` ~234: "`trip_id` is nullable … Attaching one later is a single edit" contradicts ~380-386 (no `trip_id`; the leg links the list). Make the earlier passage say what ended up true (or mark it superseded, pointing at the later section).
   - `docs/business-rules.md` ~101 "the `When` column" → 打包時機 column.
   - `docs/business-rules.md` ~113 "No date set" → 未設定日期.
   - `docs/business-rules.md` ~60 "Reaching the target quantity offers to flip it" — nothing in the UI offers that now; state what is true (the count never sets status; status is set explicitly).
   - `docs/api.md` ~181 `usage_count` "how many items" → how many rows carry the value (items, or legs for `ticket_type`).
   - `docs/api.md` ~34 "`detail` is a plain string, never a structured object" — a schema 422 is FastAPI's list; state the actual convention (refusals the routers raise are strings; schema validation 422s are FastAPI's list, which the frontend client flattens). Check whether the leg PATCH's router-raised 422 string vs the create's schema 422 list is described accurately.
   - `docs/testing.md`: mention the downgrade round-trip test alongside the from-zero and one-head tests.

## Minor, folded in by ruling

6. `tests/test_migrations_build_the_schema.py` round-trip runs on an empty DB, so the `DELETE FROM label_option WHERE kind = …` downgrade steps never meet rows. After the first upgrade, insert one `location` and one `ticket_type` label_option (plain SQL via the scratch URL), then downgrade base and upgrade head, asserting success.
7. `frontend/src/lib/departures.js` `dayTypeOf` / `nextDeparture` use the device clock (`getDay`, `getHours`). Compute weekday and minutes in Asia/Taipei via `Intl.DateTimeFormat` (as `lib/trips.js` does). Update the tests so they pass regardless of the machine TZ (use UTC instants whose Taipei time is known, e.g. 2026-09-26T00:00:00Z is Sat 08:00 Taipei).
8. `frontend/src/pages/Trip.jsx` heading 過去的行程 lists every other trip, including future ones → rename to 其他行程 (and the docs/frontend.md mention).
9. `frontend/src/pages/Trip.jsx` a leg's 起點/終點 are plain text → make them `TextCell`s like the other fields (blank refused client-side, as Transport does with `required()`).
10. `.gitignore` and `.dockerignore`: add `*.xlsx` and `backups/` to both (check each isn't already covered).
11. Docstrings still say "category and bag" only: `app/models/label_option.py` (module + class) and `app/routers/label_option.py` module docstring → name all four kinds or say "the free-text fields".
12. `app/services/sheet_import/parse.py` `as_int` raises a bare ValueError on a non-numeric 數量/價錢 — wrap at the call sites so the error names tab, row and value (as `_parse_departures` does). Test with a fixture cell `"兩個"` in 數量.
13. `frontend/src/components/Cell.jsx` QuantityCell sends `Number("1.5")` which the API rejects silently. Refuse non-integer input client-side (keep the editor open or revert, consistent with how the other cells refuse bad input) and add a vitest for the parsing helper if you extract one.

## Also

14. Delete `docs/superpowers/specs/2026-09-30-sheet-parity-design.md` and `docs/superpowers/plans/2026-09-30-sheet-parity.md` (`git rm`), in the last commit. Before deleting, confirm nothing durable in them is missing from docs/ (decisions.md, business-rules.md, data-model.md, api.md, frontend.md, sheet-import.md); move anything missing first.
