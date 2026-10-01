# Trip archive and trip templates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A trip can be archived (with an optional remark), un-archived, flagged as a 範本, and a new trip can be created as a date-shifted copy of another.

**Architecture:** Three columns on `trip` (`archived`, `archive_note`, `template`) set through the existing `PATCH /api/trips/{id}`. The current-trip rule filters out archived and template trips. `POST /api/trips` gains `copy_from_id` + `start_date`; the copy rule lives in `app/services/domain/trip.py` as `copy_legs`, which returns the legs whose packing-list link was not carried so the page can say so. The page partitions the one trip list into 其他行程 / 範本 / 已封存 using pure helpers in `frontend/src/lib/trips.js`.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, pytest; React + Vite, TanStack Query (via `hooks/useApiQuery.js`), vitest, oxlint.

**Spec:** `docs/superpowers/specs/2026-10-01-trip-archive-templates-design.md`

## Global Constraints

- Branch: `feat/trip-archive-templates` (already exists, spec committed on it). Never commit to `dev` or `main`.
- Commit messages carry **no** `Co-Authored-By`, `Claude-Session`, `Generated with` or any AI attribution. No trailers at all.
- Stage named files only (`git add <file> <file>`), never a directory; commit with `git commit -m "..." -- <same files>`.
- Every pytest run takes the machine-wide lock. Wrap every pytest command in this plan as:
  ```bash
  LOCK=/c/Users/$USERNAME/AppData/Local/Temp/anime_site_pytest.lock
  until mkdir "$LOCK" 2>/dev/null; do sleep 10; done
  venv/Scripts/python.exe -m pytest <ARGS>; rc=$?
  rmdir "$LOCK"; exit $rc
  ```
  Below, "Run pytest `<ARGS>`" means exactly that block.
- New revision id `t3rip0000003`, parent `t2rip0000002`. Before Task 1, confirm `t2rip0000002` is still the only head: `venv/Scripts/python.exe -m alembic heads`. If another head has landed on `dev`, reparent onto it.
- Migration values are written literally (no enum imports) — the house rule stated in `t2rip0000002`'s docstring.
- Leg times are Asia/Taipei; `app.constants.TAIPEI` is the zone. Taiwan has no DST.
- Error strings, exact: `"Trip to copy from not found."` (404), `"start_date is required to copy a trip with legs."` (422).
- UI strings, exact: 封存, 取消封存, 設為範本, 取消範本, 刪除行程, 封存備註, 已封存, 範本, 其他行程, 從範本, 不使用範本, 出發日期, and the notice 「{from} → {to}」在範本中連結了「{list}」，請自行連結打包清單。
- Run `venv/Scripts/ruff.exe check .` before every backend commit; `cd frontend && npm run lint && npm test` before every frontend commit.
- Doc changes land in the final task together with deleting this plan and the spec.

## Review Focus

1. **A template whose first leg departs just after Taipei midnight** (00:30, which is the previous day in UTC) — the shift must use the Taipei calendar day, or every copy lands a day off. Test in Task 3.
2. **Copying from a template that is itself archived** — the copy must be neither archived nor a template, with no `archive_note`. Test in Task 3.
3. **Archiving the trip that is current right now** — `/api/trips/current` must move to the next candidate (or 404), not keep serving the archived one. Test in Task 2.
4. **`start_date` sent without `copy_from_id`** — ignored, plain 201, not a 422. Test in Task 3.
5. **Copy request that also sends its own `notes`** — the request's `notes` wins over the source's. Test in Task 3.

---

### Task 1: The three columns, readable and patchable

**Files:**
- Create: `alembic/versions/t3rip0000003_trip_archive_template.py`
- Modify: `app/models/trip.py` (class `Trip`)
- Modify: `app/schemas/trip.py` (`TripUpdate`, `TripResponse`)
- Test: `tests/api/test_trip_router.py` (append a section)

**Interfaces:**
- Produces: `Trip.archived: bool`, `Trip.archive_note: str | None`, `Trip.template: bool`; the same three keys on every `TripResponse`; `PATCH /api/trips/{id}` accepts them, with `archived`/`template` non-nullable.

- [ ] **Step 1: Write the failing tests** — append to `tests/api/test_trip_router.py`:

```python
# --------------------------------------------------------------------------
# Archive and template flags
# --------------------------------------------------------------------------


def test_a_new_trip_is_neither_archived_nor_a_template(client, trip):
    assert (trip["archived"], trip["archive_note"], trip["template"]) == (False, None, False)


def test_a_trip_can_be_archived_with_a_remark_and_unarchived(client, trip):
    url = f"/api/trips/{trip['id']}"
    body = client.patch(url, json={"archived": True, "archive_note": "下次早點訂票"}).json()
    assert (body["archived"], body["archive_note"]) == (True, "下次早點訂票")
    body = client.patch(url, json={"archived": False}).json()
    # Un-archiving leaves the remark alone.
    assert (body["archived"], body["archive_note"]) == (False, "下次早點訂票")
    assert client.patch(url, json={"archive_note": None}).json()["archive_note"] is None


def test_a_trip_can_be_made_a_template_and_back(client, trip):
    url = f"/api/trips/{trip['id']}"
    assert client.patch(url, json={"template": True}).json()["template"] is True
    assert client.patch(url, json={"template": False}).json()["template"] is False


@pytest.mark.parametrize("field", ["archived", "template"])
def test_a_null_archive_or_template_flag_is_a_422(client, trip, field):
    assert client.patch(f"/api/trips/{trip['id']}", json={field: None}).status_code == 422
```

- [ ] **Step 2: Run them to see them fail**

Run pytest `tests/api/test_trip_router.py -q -k "archived or template or archive"`
Expected: FAIL — `KeyError: 'archived'` on the response, and the PATCH ignores the unknown fields.

- [ ] **Step 3: Write the migration** — `alembic/versions/t3rip0000003_trip_archive_template.py`:

```python
"""a trip can be archived, with a remark, and can be a template

`archived` hides a past trip from 其他行程 and from the current-trip rule;
`archive_note` is the after-the-fact remark, separate from the planning
`notes`; `template` offers the trip as a starting point for a new one. The two
flags are independent, like `saved` and `template` on a packing list.

Revision ID: t3rip0000003
Revises: t2rip0000002
Create Date: 2026-10-01

"""

import sqlalchemy as sa

from alembic import op

revision = "t3rip0000003"
down_revision = "t2rip0000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trip", sa.Column("archived", sa.Boolean(), server_default="false", nullable=False)
    )
    op.add_column("trip", sa.Column("archive_note", sa.Text(), nullable=True))
    op.add_column(
        "trip", sa.Column("template", sa.Boolean(), server_default="false", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("trip", "template")
    op.drop_column("trip", "archive_note")
    op.drop_column("trip", "archived")
```

- [ ] **Step 4: Add the model columns** — in `app/models/trip.py`, inside `class Trip`, after `notes`:

```python
    # `archived` takes a trip out of 其他行程 and out of the current-trip rule;
    # it locks nothing and is undone by clearing it. `archive_note` is the
    # remark written afterwards, kept apart from the planning `notes`.
    # `template` offers the trip as a starting point. Independent, like
    # `PackingList.saved` and `.template`.
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    archive_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    template: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
```

(`Boolean` and `Text` are already imported in that file.)

- [ ] **Step 5: Add the schema fields** — in `app/schemas/trip.py` replace `TripUpdate` and `TripResponse` with:

```python
class TripUpdate(NonNullableUpdate):
    non_nullable = ("name", "archived", "template")

    name: str | None = Field(default=None, min_length=1)
    notes: str | None = None
    archived: bool | None = None
    archive_note: str | None = None
    template: bool | None = None


class TripResponse(TripBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    archived: bool
    archive_note: str | None = None
    template: bool
    legs: list[TripLegResponse] = []
```

- [ ] **Step 6: Run the new tests and the whole trip file**

Run pytest `tests/api/test_trip_router.py tests/test_migrations_build_the_schema.py -q`
Expected: PASS (the migration tests cover from-zero, one head, and downgrade-to-base-and-back including the new revision).

- [ ] **Step 7: Lint and commit**

```bash
venv/Scripts/ruff.exe check .
git add alembic/versions/t3rip0000003_trip_archive_template.py app/models/trip.py app/schemas/trip.py tests/api/test_trip_router.py
git commit -m "feat: a trip can be archived with a remark, and flagged as a template" -- alembic/versions/t3rip0000003_trip_archive_template.py app/models/trip.py app/schemas/trip.py tests/api/test_trip_router.py
```

---

### Task 2: Archived and template trips are never current

**Files:**
- Modify: `app/services/domain/trip.py` (`current_trip`)
- Test: `tests/api/test_trip_router.py` (the "current trip" section; extend `make_trip`)

**Interfaces:**
- Consumes: `Trip.archived`, `Trip.template` (Task 1).
- Produces: `current_trip(db, now)` — same signature — ignores trips with either flag set.

- [ ] **Step 1: Write the failing tests.** First give `make_trip` keyword flags — replace it in `tests/api/test_trip_router.py`:

```python
def make_trip(db, name, *offsets_hours, **flags):
    trip = Trip(name=name, **flags)
    db.add(trip)
    db.flush()
    for hours in offsets_hours:
        start = NOW + timedelta(hours=hours)
        db.add(TripLeg(trip_id=trip.id, from_place="a", to_place="b",
                       departs_at=start, arrives_at=start + timedelta(hours=1)))
    db.flush()
    return trip
```

Then append after `test_a_tie_goes_to_the_newer_trip`:

```python
# Each refusal below gives the flagged trip the SOONEST leg ahead, so without
# the exclusion it would be current: the fixture is what lets the test fail.
# The mirror un-flags the same trip and expects it back.


@pytest.mark.parametrize("flag", ["archived", "template"])
def test_a_flagged_trip_is_never_current(db_session, flag):
    later = make_trip(db_session, "later", 72)
    flagged = make_trip(db_session, "flagged", 24, **{flag: True})
    assert current_trip(db_session, NOW).id == later.id
    setattr(flagged, flag, False)
    db_session.flush()
    assert current_trip(db_session, NOW).id == flagged.id


@pytest.mark.parametrize("flag", ["archived", "template"])
def test_with_every_trip_flagged_there_is_no_current_trip(db_session, flag):
    make_trip(db_session, "only", 24, **{flag: True})
    assert current_trip(db_session, NOW) is None


def test_archiving_the_current_trip_moves_the_current_endpoint(client):
    far = datetime.now(timezone.utc) + timedelta(days=30)
    soon = client.post("/api/trips", json={"name": "soon"}).json()
    later = client.post("/api/trips", json={"name": "later"}).json()
    add_leg(client, soon, departs=far.isoformat(), arrives=(far + timedelta(hours=1)).isoformat())
    add_leg(client, later, departs=(far + timedelta(days=1)).isoformat(),
            arrives=(far + timedelta(days=1, hours=1)).isoformat())
    assert client.get("/api/trips/current").json()["id"] == soon["id"]
    client.patch(f"/api/trips/{soon['id']}", json={"archived": True})
    assert client.get("/api/trips/current").json()["id"] == later["id"]
```

- [ ] **Step 2: Run to see them fail**

Run pytest `tests/api/test_trip_router.py -q -k "flagged or archiving_the_current"`
Expected: FAIL — the flagged trip is still returned as current.

- [ ] **Step 3: Implement** — in `app/services/domain/trip.py`, change the docstring's first line and the query:

```python
def current_trip(db: Session, now: datetime) -> Trip | None:
    """The trip with the soonest leg still ahead; failing that, the one whose
    legs ended most recently. Ties go to the newer trip (higher id). A trip
    with no legs is never current, and neither is an archived trip or a
    template — the one is finished with and the other is not a journey.

    Computed in Python over every trip: there are a handful, and the rule reads
    more plainly here than as SQL.
    """
    trips = (
        db.execute(
            select(Trip)
            .where(Trip.archived.is_(False), Trip.template.is_(False))
            .options(selectinload(Trip.legs))
        )
        .scalars()
        .all()
    )
```

(the rest of the function is unchanged).

- [ ] **Step 4: Run the trip file**

Run pytest `tests/api/test_trip_router.py -q`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
venv/Scripts/ruff.exe check .
git add app/services/domain/trip.py tests/api/test_trip_router.py
git commit -m "feat: archived and template trips are never the current trip" -- app/services/domain/trip.py tests/api/test_trip_router.py
```

---

### Task 3: Creating a trip as a copy of another

**Files:**
- Modify: `app/services/domain/trip.py` (add `copy_legs`)
- Modify: `app/schemas/trip.py` (add `TripCreate`, `UnlinkedLeg`, `TripCreated`)
- Modify: `app/routers/trip.py` (`create_trip`, new constants)
- Test: `tests/api/test_trip_copy.py` (create)

**Interfaces:**
- Consumes: the three columns (Task 1).
- Produces:
  - `copy_legs(db: Session, source: Trip, target: Trip, start_date: date | None) -> list[dict]` — adds the copied legs (flushes nothing itself beyond `db.add`), returns `[{"from_place", "to_place", "packing_list_name"}]` for each source leg that had a list, in leg order.
  - `POST /api/trips` body `TripCreate` = `name`, `notes`, `copy_from_id: int | None`, `start_date: date | None`; response `TripCreated` = `TripResponse` + `unlinked_from: list[UnlinkedLeg]`.

- [ ] **Step 1: Write the failing tests** — `tests/api/test_trip_copy.py`:

```python
"""Creating a trip from another: the definition carries, the state resets,
and the legs move to the chosen start date."""

from datetime import datetime

import pytest

TPE = "+08:00"


def at(value):
    """An instant, whatever offset the API chose to serialise it in."""
    return datetime.fromisoformat(value)


def make_source(client):
    """A source trip with every reset field SET, so a reset that fails to
    happen shows up: ticked, coded, seated, linked, archived, templated."""
    source = client.post("/api/trips", json={"name": "範本", "notes": "帶身分證"}).json()
    lst = client.post("/api/packing-lists", json={"name": "台北去彰化", "saved": True}).json()
    legs = [
        # Crosses Taipei midnight, and departs at 23:30 Taipei = 15:30 UTC.
        {"from_place": "台北車站", "to_place": "彰化火車站",
         "departs_at": f"2026-09-24T23:30:00{TPE}", "arrives_at": f"2026-09-25T01:10:00{TPE}",
         "service": "火車 - 自強", "service_number": "5158", "seat": "5車15號", "price": 550,
         "ticket_type": "電子", "booked": True, "paid": True, "collected": True,
         "booking_code": "0589115", "notes": "靠窗", "packing_list_id": lst["id"]},
        {"from_place": "彰化火車站", "to_place": "台北車站",
         "departs_at": f"2026-09-28T12:15:00{TPE}", "arrives_at": f"2026-09-28T14:23:00{TPE}",
         "booked": True, "booking_code": "1234567"},
    ]
    for leg in legs:
        assert client.post(f"/api/trips/{source['id']}/legs", json=leg).status_code == 201
    client.patch(f"/api/trips/{source['id']}",
                 json={"template": True, "archived": True, "archive_note": "舊的"})
    return client.get(f"/api/trips/{source['id']}").json()


def copy(client, source, **body):
    return client.post("/api/trips", json={"name": "新行程", "copy_from_id": source["id"], **body})


def test_the_definition_carries_and_the_state_resets(client):
    source = make_source(client)
    response = copy(client, source, start_date="2026-10-08")
    assert response.status_code == 201
    new = response.json()

    assert (new["name"], new["notes"]) == ("新行程", "帶身分證")
    assert (new["archived"], new["archive_note"], new["template"]) == (False, None, False)

    first, second = new["legs"]
    assert (first["from_place"], first["to_place"]) == ("台北車站", "彰化火車站")
    assert (first["service"], first["service_number"], first["price"], first["ticket_type"],
            first["notes"]) == ("火車 - 自強", "5158", 550, "電子", "靠窗")
    for leg in (first, second):
        assert (leg["booked"], leg["paid"], leg["collected"]) == (False, False, False)
        assert (leg["booking_code"], leg["seat"], leg["packing_list_id"]) == (None, None, None)
    assert {leg["trip_id"] for leg in new["legs"]} == {new["id"]}


def test_the_legs_move_to_the_start_date_keeping_clock_and_gaps(client):
    source = make_source(client)
    new = copy(client, source, start_date="2026-10-08").json()
    first, second = new["legs"]
    # Taipei day 09-24 → 10-08 is +14 days, and the midnight crossing survives.
    assert at(first["departs_at"]) == at(f"2026-10-08T23:30:00{TPE}")
    assert at(first["arrives_at"]) == at(f"2026-10-09T01:10:00{TPE}")
    assert at(second["departs_at"]) == at(f"2026-10-12T12:15:00{TPE}")  # still four days later


def test_the_shift_reads_the_taipei_day_not_the_utc_one(client):
    source = client.post("/api/trips", json={"name": "s"}).json()
    # 00:30 Taipei on 09-24 is 16:30 UTC on 09-23.
    client.post(f"/api/trips/{source['id']}/legs", json={
        "from_place": "a", "to_place": "b",
        "departs_at": f"2026-09-24T00:30:00{TPE}", "arrives_at": f"2026-09-24T02:00:00{TPE}"})
    new = copy(client, source, start_date="2026-10-05").json()
    assert at(new["legs"][0]["departs_at"]) == at(f"2026-10-05T00:30:00{TPE}")


def test_the_shift_can_go_backwards(client):
    source = make_source(client)
    new = copy(client, source, start_date="2026-09-01").json()
    assert at(new["legs"][0]["departs_at"]) == at(f"2026-09-01T23:30:00{TPE}")


def test_unlinked_from_names_exactly_the_legs_that_had_a_list(client):
    source = make_source(client)
    new = copy(client, source, start_date="2026-10-08").json()
    assert new["unlinked_from"] == [
        {"from_place": "台北車站", "to_place": "彰化火車站", "packing_list_name": "台北去彰化"}
    ]


def test_a_plain_create_has_an_empty_unlinked_from(client):
    assert client.post("/api/trips", json={"name": "x"}).json()["unlinked_from"] == []


def test_the_source_is_unchanged(client):
    source = make_source(client)
    copy(client, source, start_date="2026-10-08")
    assert client.get(f"/api/trips/{source['id']}").json() == source


def test_a_source_with_legs_and_no_start_date_is_a_422_and_writes_nothing(client):
    source = make_source(client)
    before = len(client.get("/api/trips").json())
    response = copy(client, source)
    assert response.status_code == 422
    assert response.json()["detail"] == "start_date is required to copy a trip with legs."
    assert len(client.get("/api/trips").json()) == before


def test_an_unknown_source_is_a_404_and_writes_nothing(client):
    before = len(client.get("/api/trips").json())
    response = client.post("/api/trips", json={"name": "x", "copy_from_id": 999999,
                                               "start_date": "2026-10-08"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Trip to copy from not found."
    assert len(client.get("/api/trips").json()) == before


def test_a_legless_source_needs_no_start_date(client):
    source = client.post("/api/trips", json={"name": "空", "notes": "n"}).json()
    response = copy(client, source)
    assert response.status_code == 201
    assert (response.json()["notes"], response.json()["legs"]) == ("n", [])


def test_a_start_date_without_a_source_is_ignored(client):
    response = client.post("/api/trips", json={"name": "x", "start_date": "2026-10-08"})
    assert response.status_code == 201


def test_the_requests_own_notes_win_over_the_sources(client):
    source = make_source(client)
    new = copy(client, source, start_date="2026-10-08", notes="我的").json()
    assert new["notes"] == "我的"


@pytest.mark.parametrize("bad", ["2026-13-01", "not a date"])
def test_a_malformed_start_date_is_a_422(client, bad):
    source = make_source(client)
    assert copy(client, source, start_date=bad).status_code == 422
```

- [ ] **Step 2: Run to see them fail**

Run pytest `tests/api/test_trip_copy.py -q`
Expected: FAIL — `copy_from_id` is ignored, no legs are copied, no `unlinked_from` key.

- [ ] **Step 3: Add the schemas** — in `app/schemas/trip.py`, add `from datetime import date` at the top, and after `TripResponse`:

```python
class TripCreate(TripBase):
    """`copy_from_id` copies another trip; `start_date` is the Taipei day its
    first leg moves to, required when that trip has legs."""

    copy_from_id: int | None = None
    start_date: date | None = None


class UnlinkedLeg(BaseModel):
    """A source leg whose packing list the copy did not carry."""

    from_place: str
    to_place: str
    packing_list_name: str


class TripCreated(TripResponse):
    unlinked_from: list[UnlinkedLeg] = []
```

- [ ] **Step 4: Add the rule** — in `app/services/domain/trip.py`, change the imports and append `copy_legs`:

```python
"""Which trip is "This time", and what a copied trip carries."""

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.constants import TAIPEI
from app.models import Trip, TripLeg
```

```python
def copy_legs(db: Session, source: Trip, target: Trip, start_date: date | None) -> list[dict]:
    """Copy `source`'s legs onto `target`: definition carries, state resets.

    Every leg moves by the whole days between `start_date` and the Taipei
    calendar day of the source's earliest departure, so clock times and the
    gaps between legs survive. Taiwan keeps no daylight saving, so a whole-day
    shift never moves a clock time.

    Booking state, the booking code and the seat belong to one booking and
    reset. The packing-list link cannot carry - a list is linked from at most
    one leg - so it resets too, and the legs that had one are returned for the
    caller to report.
    """
    if not source.legs:
        return []
    first_day = min(leg.departs_at for leg in source.legs).astimezone(TAIPEI).date()
    shift = timedelta(days=(start_date - first_day).days)
    unlinked = []
    for leg in source.legs:
        db.add(
            TripLeg(
                trip_id=target.id,
                # Carried: the journey.
                from_place=leg.from_place,
                to_place=leg.to_place,
                departs_at=leg.departs_at + shift,
                arrives_at=leg.arrives_at + shift,
                service=leg.service,
                service_number=leg.service_number,
                price=leg.price,
                ticket_type=leg.ticket_type,
                notes=leg.notes,
                # Reset: what was true of the old booking.
                booked=False,
                paid=False,
                collected=False,
                booking_code=None,
                seat=None,
                packing_list_id=None,
            )
        )
        if leg.packing_list is not None:
            unlinked.append(
                {
                    "from_place": leg.from_place,
                    "to_place": leg.to_place,
                    "packing_list_name": leg.packing_list.name,
                }
            )
    return unlinked
```

- [ ] **Step 5: Wire the router** — in `app/routers/trip.py`:

Add to the schema import list `TripCreate`, `TripCreated` (keep `TripBase` only if still used elsewhere in the file — after this change it is not, so remove it). Change the domain import to:

```python
from app.services.domain.trip import copy_legs, current_trip
```

Add constants beside the others:

```python
COPY_SOURCE_NOT_FOUND = "Trip to copy from not found."
START_DATE_REQUIRED = "start_date is required to copy a trip with legs."
```

Replace `create_trip`:

```python
@router.post("/api/trips", response_model=TripCreated, status_code=201)
def create_trip(payload: TripCreate, db: Session = Depends(get_db)):
    source = None
    if payload.copy_from_id is not None:
        # Both refusals come before anything is written.
        source = db.scalars(_trips_query().where(Trip.id == payload.copy_from_id)).first()
        if source is None:
            raise HTTPException(status_code=404, detail=COPY_SOURCE_NOT_FOUND)
        if source.legs and payload.start_date is None:
            raise HTTPException(status_code=422, detail=START_DATE_REQUIRED)

    trip = Trip(**payload.model_dump(exclude={"copy_from_id", "start_date"}))
    if source is not None and "notes" not in payload.model_fields_set:
        trip.notes = source.notes
    db.add(trip)
    db.flush()

    unlinked = copy_legs(db, source, trip, payload.start_date) if source is not None else []
    db.commit()
    created = TripResponse.model_validate(_get_trip(db, trip.id))
    return TripCreated(**created.model_dump(), unlinked_from=unlinked)
```

- [ ] **Step 6: Run the copy tests and the trip file**

Run pytest `tests/api/test_trip_copy.py tests/api/test_trip_router.py -q`
Expected: PASS. If `test_the_source_is_unchanged` fails on `updated_at`-like fields, it is not one — `TripResponse` has no timestamps; investigate any real diff.

- [ ] **Step 7: Run the whole suite** (the sheet import creates trips through the model, not the endpoint, but confirm)

Run pytest `-q`
Expected: PASS, except the three known `python3`-stub failures only if this suite has them (it does not; those are the platform's).

- [ ] **Step 8: Lint and commit**

```bash
venv/Scripts/ruff.exe check .
git add app/services/domain/trip.py app/schemas/trip.py app/routers/trip.py tests/api/test_trip_copy.py
git commit -m "feat: a trip can be created as a date-shifted copy of another" -- app/services/domain/trip.py app/schemas/trip.py app/routers/trip.py tests/api/test_trip_copy.py
```

---

### Task 4: Frontend helpers for sections, the copy form and the notice

**Files:**
- Modify: `frontend/src/lib/trips.js`
- Test: `frontend/src/lib/trips.test.js`

The repository's frontend suite tests `lib/` only (see `docs/testing.md`, "The frontend suite"); page logic worth testing is pulled into `lib/` for that reason, so the spec's "vitest covers the page sections, dialog, date input and notice" is met by testing these helpers.

**Interfaces:**
- Produces:
  - `partitionTrips(trips, excludeId) -> { others, templates, archived }` — `excludeId` (number or null) is left out of all three; archived wins over template; order preserved.
  - `templateChoices(trips) -> trip[]` — every trip with `template`, archived or not, order preserved.
  - `needsStartDate(trip) -> boolean` — the trip has legs.
  - `unlinkedNotice(entry) -> string`.
  - `archivePatch(note) -> { archived: true, archive_note: string | null }` — trims; blank is null.
  - `firstLine(text) -> string | null`.

- [ ] **Step 1: Write the failing tests** — add to the import list in `trips.test.js`: `archivePatch, firstLine, needsStartDate, partitionTrips, templateChoices, unlinkedNotice`, and append:

```js
const t = (id, fields = {}) => ({ id, archived: false, template: false, legs: [], ...fields })

describe('partitionTrips', () => {
  it('puts each trip in exactly one section, archived winning over template', () => {
    const trips = [t(1), t(2, { template: true }), t(3, { archived: true }),
      t(4, { archived: true, template: true }), t(5)]
    const { others, templates, archived } = partitionTrips(trips, 5)
    expect(others.map((x) => x.id)).toEqual([1])
    expect(templates.map((x) => x.id)).toEqual([2])
    expect(archived.map((x) => x.id)).toEqual([3, 4])
  })
  it('excludes nothing when no trip is on screen', () => {
    expect(partitionTrips([t(1)], null).others).toHaveLength(1)
  })
})

describe('templateChoices', () => {
  it('offers every template, archived or not', () => {
    const trips = [t(1), t(2, { template: true }), t(3, { template: true, archived: true })]
    expect(templateChoices(trips).map((x) => x.id)).toEqual([2, 3])
  })
})

describe('needsStartDate', () => {
  it('is true only for a trip with legs', () => {
    expect(needsStartDate(t(1))).toBe(false)
    expect(needsStartDate(t(1, { legs: [{}] }))).toBe(true)
  })
})

describe('unlinkedNotice', () => {
  it('names the leg and the list', () => {
    expect(unlinkedNotice({ from_place: '台北車站', to_place: '彰化火車站', packing_list_name: '台北去彰化' }))
      .toBe('「台北車站 → 彰化火車站」在範本中連結了「台北去彰化」，請自行連結打包清單。')
  })
})

describe('archivePatch', () => {
  it('trims the remark and sends a blank one as null', () => {
    expect(archivePatch('  下次早點訂  ')).toEqual({ archived: true, archive_note: '下次早點訂' })
    expect(archivePatch('   ')).toEqual({ archived: true, archive_note: null })
  })
})

describe('firstLine', () => {
  it('is the first non-empty line, or null', () => {
    expect(firstLine('a\nb')).toBe('a')
    expect(firstLine('\n  \nb')).toBe('b')
    expect(firstLine(null)).toBe(null)
  })
})
```

- [ ] **Step 2: Run to see them fail**

Run: `cd frontend && npm test`
Expected: FAIL — the imports are undefined.

- [ ] **Step 3: Implement** — append to `frontend/src/lib/trips.js`:

```js
/**
 * Every trip but the one on screen, in the page's three sections. An archived
 * template is shown as archived: it is finished with, and still offered by
 * `templateChoices`.
 */
export function partitionTrips(trips, excludeId) {
  const others = []
  const templates = []
  const archived = []
  for (const trip of trips) {
    if (trip.id === excludeId) continue
    if (trip.archived) archived.push(trip)
    else if (trip.template) templates.push(trip)
    else others.push(trip)
  }
  return { others, templates, archived }
}

/** What 從範本 offers: every template, archived or not. */
export function templateChoices(trips) {
  return trips.filter((trip) => trip.template)
}

/** A copy needs a start date only when there are legs to move. */
export function needsStartDate(trip) {
  return trip.legs.length > 0
}

/** One line per template leg whose packing list the copy did not carry. */
export function unlinkedNotice({ from_place: from, to_place: to, packing_list_name: list }) {
  return `「${from} → ${to}」在範本中連結了「${list}」，請自行連結打包清單。`
}

/** The PATCH body for 封存: the remark trimmed, blank as null. */
export function archivePatch(note) {
  return { archived: true, archive_note: note.trim() || null }
}

export function firstLine(text) {
  if (!text) return null
  return text.split('\n').find((line) => line.trim()) ?? null
}
```

- [ ] **Step 4: Run tests and lint**

Run: `cd frontend && npm test && npm run lint`
Expected: PASS, no lint errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/trips.js frontend/src/lib/trips.test.js
git commit -m "feat: trip helpers for sections, template copies and the archive remark" -- frontend/src/lib/trips.js frontend/src/lib/trips.test.js
```

---

### Task 5: The page — menu, archive dialog, badges, sections, create from template, notice

**Files:**
- Modify: `frontend/src/pages/Trip.jsx`

**Interfaces:**
- Consumes: Task 4's helpers; Task 1's response fields; Task 3's `POST` body and `unlinked_from`.
- Uses `RowMenu` (`components/RowMenu.jsx`, props `open`, `onClose`, `actions: [{label, danger?, onSelect}]`) directly in place of `DeleteMenu` for the trip header. `DeleteMenu` stays for leg cards.

- [ ] **Step 1: Imports.** In `Trip.jsx`:
  - `import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'`
  - `import { RowMenu } from '../components/RowMenu'`
  - extend the `../lib/trips` import with `archivePatch, firstLine, needsStartDate, partitionTrips, templateChoices, unlinkedNotice`.

- [ ] **Step 2: The trip menu.** Add after `Problem`:

```jsx
/** The trip header's ⋯: archive, template, delete. */
function TripMenu({ trip, onArchive, onUnarchive, onToggleTemplate, onDelete }) {
  const [open, setOpen] = useState(false)
  const actions = [
    trip.archived ? { label: '取消封存', onSelect: onUnarchive } : { label: '封存', onSelect: onArchive },
    { label: trip.template ? '取消範本' : '設為範本', onSelect: onToggleTemplate },
    { label: '刪除行程', danger: true, onSelect: onDelete },
  ]
  return (
    <>
      <button
        type="button"
        aria-label={`${trip.name} 的選單`}
        aria-haspopup="menu"
        onClick={() => setOpen(true)}
        className="px-2 text-text-faint hover:text-text"
        style={{ minHeight: 0 }}
      >
        ⋯
      </button>
      <RowMenu open={open} onClose={() => setOpen(false)} actions={actions} />
    </>
  )
}
```

- [ ] **Step 3: The archive dialog** (ConfirmDialog's markup, plus a textarea). Add after `TripMenu`:

```jsx
/** 封存, with the optional remark. Starts from any remark already written. */
function ArchiveDialog({ trip, onConfirm, onCancel }) {
  const [note, setNote] = useState(trip.archive_note ?? '')
  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-ink/50 p-0 sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="archive-title"
    >
      <div className="w-full max-w-md rounded-t-2xl border border-border bg-surface p-5 sm:rounded-2xl">
        <h2 id="archive-title" className="m-0 text-base font-semibold">
          封存「{trip.name}」？
        </h2>
        <p className="mt-2 text-sm text-text-muted">
          封存的行程會移到「已封存」，隨時可以取消封存。
        </p>
        <textarea
          autoFocus
          aria-label="封存備註"
          placeholder="封存備註（選填）"
          value={note}
          onChange={(event) => setNote(event.target.value)}
          rows={3}
          className={`${inputClass} mt-3 w-full`}
        />
        <div className="mt-5 flex flex-col gap-2">
          <button
            type="button"
            onClick={() => onConfirm(archivePatch(note))}
            className="rounded-md bg-brand px-4 font-medium text-on-brand"
          >
            封存
          </button>
          <button type="button" onClick={onCancel} className="px-4 text-text-muted">
            取消
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: CreateTrip takes a template and a date.** Replace `CreateTrip`:

```jsx
/**
 * A name field, an optional 從範本 and + 新增行程. A template with legs needs
 * a 出發日期, the Taipei day its first leg moves to. With `onCancel`, Escape
 * and 取消 close it.
 */
function CreateTrip({ templates = [], onCreate, onCancel, autoFocus = false, className = 'justify-center' }) {
  const [name, setName] = useState('')
  const [templateId, setTemplateId] = useState('')
  const [startDate, setStartDate] = useState('')
  const template = templates.find((row) => String(row.id) === templateId)
  const dateNeeded = template ? needsStartDate(template) : false
  const ready = name.trim() && (!dateNeeded || startDate)

  const submit = () => {
    if (!ready) return
    const payload = { name: name.trim() }
    if (template) {
      payload.copy_from_id = template.id
      if (dateNeeded) payload.start_date = startDate
    }
    onCreate(payload)
  }
  return (
    <div className={`flex flex-wrap items-center gap-2 ${className}`}>
      <input
        autoFocus={autoFocus}
        aria-label="行程名稱"
        placeholder="行程名稱"
        value={name}
        onChange={(event) => setName(event.target.value)}
        onKeyDown={keysFor(submit, onCancel ?? (() => setName('')))}
        className={`${inputClass} w-48`}
      />
      {templates.length > 0 && (
        <select
          aria-label="從範本"
          value={templateId}
          onChange={(event) => setTemplateId(event.target.value)}
          className={inputClass}
        >
          <option value="">不使用範本</option>
          {templates.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </select>
      )}
      {dateNeeded && (
        <input
          type="date"
          aria-label="出發日期"
          value={startDate}
          onChange={(event) => setStartDate(event.target.value)}
          className={inputClass}
        />
      )}
      <button type="button" disabled={!ready} onClick={submit} className={smallButton}>
        + 新增行程
      </button>
      {onCancel && (
        <button type="button" onClick={onCancel} className={smallButton}>
          取消
        </button>
      )}
    </div>
  )
}
```

`NewTrip` gains a `templates` prop and passes it to `<CreateTrip templates={templates} ... />`.

- [ ] **Step 5: The three sections.** Replace `OtherTrips` with:

```jsx
function TripLinks({ trips, note = false }) {
  return (
    <ul className="m-0 mt-2 list-none p-0">
      {trips.map((trip) => (
        <li key={trip.id}>
          <Link to={`/trips/${trip.id}`} className="flex justify-between gap-3 py-1.5 text-brand">
            <span className="min-w-0">
              {trip.name}
              {note && trip.archive_note && (
                <span className="ml-2 text-sm text-text-faint">{firstLine(trip.archive_note)}</span>
              )}
            </span>
            <span className="shrink-0 text-text-faint tabular-nums">
              {tripDateRange(trip.legs) ?? '沒有行程段'}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  )
}

/**
 * Every trip but the one on screen: 其他行程 (past and future alike, so not
 * "past"), 範本, and 已封存 collapsed. With `onCreate` 其他行程 is shown even
 * when empty, to hold + 新增行程.
 */
function TripSections({ trips, currentId, templates, onCreate }) {
  const { others, templates: templateTrips, archived } = partitionTrips(trips, currentId)
  return (
    <>
      {(others.length > 0 || onCreate) && (
        <section className="mt-10 border-t border-border pt-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="m-0 text-base font-semibold">其他行程</h2>
            {onCreate && <NewTrip templates={templates} onCreate={onCreate} />}
          </div>
          <TripLinks trips={others} />
        </section>
      )}
      {templateTrips.length > 0 && (
        <section className="mt-6 border-t border-border pt-4">
          <h2 className="m-0 text-base font-semibold">範本</h2>
          <TripLinks trips={templateTrips} />
        </section>
      )}
      {archived.length > 0 && (
        <details className="mt-6 border-t border-border pt-4">
          <summary className="cursor-pointer text-base font-semibold">
            已封存（{archived.length}）
          </summary>
          <TripLinks trips={archived} note />
        </details>
      )}
    </>
  )
}
```

- [ ] **Step 6: The notice.** Add:

```jsx
/** After a copy: which template legs had a packing list the copy did not carry. */
function UnlinkedNotice({ entries }) {
  const [open, setOpen] = useState(true)
  if (!open || !entries?.length) return null
  return (
    <div role="status" className="mt-3 rounded-md border border-border-strong bg-surface-2 p-3 text-sm">
      {entries.map((entry) => (
        <p key={`${entry.from_place}-${entry.to_place}-${entry.packing_list_name}`} className="m-0">
          {unlinkedNotice(entry)}
        </p>
      ))}
      <button type="button" onClick={() => setOpen(false)} className={`${smallButton} mt-2`}>
        知道了
      </button>
    </div>
  )
}
```

- [ ] **Step 7: TripView.** Replace its signature and header, and add the dialog state. The new `TripView`:

```jsx
function TripView({ trip, allTrips, templates, unlinked, ticketTypes, actions, onCreateTrip, onDeleted }) {
  const [confirming, setConfirming] = useState(false)
  const [archiving, setArchiving] = useState(false)
  const legs = sortLegs(trip.legs)
  const patchTrip = (changes) => actions.patchTrip.mutate({ id: trip.id, changes })

  return (
    <>
      <div className="flex items-center justify-between gap-2">
        <h1 className="m-0 flex min-w-0 flex-1 items-center gap-2 text-xl font-semibold">
          <span className="min-w-0 flex-1">
            <TextCell
              value={trip.name}
              placeholder="行程名稱"
              onCommit={required((name) => patchTrip({ name }))}
            />
          </span>
          {trip.archived && (
            <span className="shrink-0 rounded-sm bg-surface-2 px-2 text-xs font-normal text-text-muted">已封存</span>
          )}
          {trip.template && (
            <span className="shrink-0 rounded-sm bg-surface-2 px-2 text-xs font-normal text-text-muted">範本</span>
          )}
        </h1>
        <TripMenu
          trip={trip}
          onArchive={() => setArchiving(true)}
          onUnarchive={() => patchTrip({ archived: false })}
          onToggleTemplate={() => patchTrip({ template: !trip.template })}
          onDelete={() => setConfirming(true)}
        />
      </div>
      <TextCell value={trip.notes} placeholder="備註" onCommit={(notes) => patchTrip({ notes })} />
      {(trip.archived || trip.archive_note) && (
        <TextCell
          value={trip.archive_note}
          placeholder="封存備註"
          onCommit={(archive_note) => patchTrip({ archive_note })}
        />
      )}
      <UnlinkedNotice entries={unlinked} />

      <div className="mt-4 flex flex-col gap-3">
        {legs.length === 0 && <EmptyState>這個行程還沒有任何一段。</EmptyState>}
        {legs.map((leg) => (
          <LegCard key={leg.id} leg={leg} ticketTypes={ticketTypes} actions={actions} />
        ))}
        <AddLeg onAdd={(payload) => actions.addLeg.mutateAsync({ tripId: trip.id, payload })} />
      </div>

      <TripSections trips={allTrips} currentId={trip.id} templates={templates} onCreate={onCreateTrip} />

      {archiving && (
        <ArchiveDialog
          trip={trip}
          onConfirm={(changes) => {
            setArchiving(false)
            patchTrip(changes)
          }}
          onCancel={() => setArchiving(false)}
        />
      )}
      {confirming && (
        <ConfirmDialog
          title={`刪除「${trip.name}」？`}
          body="這個行程和它所有的行程段都會一起刪除，連結的打包清單不受影響。"
          confirmLabel="刪除"
          onConfirm={() => {
            setConfirming(false)
            actions.deleteTrip.mutate(trip.id, { onSuccess: onDeleted })
          }}
          onCancel={() => setConfirming(false)}
        />
      )}
    </>
  )
}
```

Remove the now-unused `DeleteMenu` import only if no leg card uses it — `LegCard` still does, so keep it.

- [ ] **Step 8: The page component.** In `export default function Trip()`:
  - add `const location = useLocation()`;
  - replace `openNewTrip`:

```jsx
  const openNewTrip = (payload) =>
    createTrip.mutate(payload, {
      // A trip with no legs is never the current one, and a copy may not be
      // either, so the new trip is opened by its own address. What the copy
      // could not carry rides along in the navigation state.
      onSuccess: (created) =>
        navigate(`/trips/${created.id}`, { state: { unlinked: created.unlinked_from } }),
    })
```

  - compute after `options`: `const templates = templateChoices(all.data ?? [])`
  - the no-current-trip branch becomes:

```jsx
    return shell(
      <>
        <h1 className="m-0 text-xl font-semibold">This time</h1>
        <EmptyState action={<CreateTrip templates={templates} onCreate={openNewTrip} />}>
          還沒有進行中的行程。
        </EmptyState>
        <TripSections trips={all.data ?? []} currentId={null} templates={templates} />
      </>,
    )
```

  - delete the `otherTrips` line and render:

```jsx
  return shell(
    <TripView
      key={trip.data.id}
      trip={trip.data}
      allTrips={all.data ?? []}
      templates={templates}
      unlinked={location.state?.unlinked}
      ticketTypes={ticketTypes}
      actions={actions}
      onCreateTrip={openNewTrip}
      onDeleted={() => navigate('/trip')}
    />,
  )
```

  - update the file's header comment: after "…the three ticks are the exceptions…", add a sentence: "A trip can be archived (with a remark) or made a 範本 from its ⋯ menu; the trips below it are split into 其他行程, 範本 and a collapsed 已封存."

- [ ] **Step 9: Lint, test, build**

Run: `cd frontend && npm run lint && npm test && npm run build`
Expected: no lint errors, vitest PASS, build writes `frontend_dist/`.

- [ ] **Step 10: See it work.** Start `.\dev.ps1` (uvicorn :8002, Vite :5175; ensure the local `travel` DB is migrated: `venv/Scripts/python.exe -m alembic upgrade head`). In the browser at `http://localhost:5175/trip`:
  1. ⋯ → 設為範本 on a trip with legs: 範本 badge appears; on another trip's page it is listed under 範本.
  2. + 新增行程, choose it under 從範本: 出發日期 appears and + 新增行程 is disabled until it is set. Create: the new trip opens with legs on the new dates, no ticks/code/seat, and the notice if any leg had a list. 知道了 hides it.
  3. ⋯ → 封存 with a remark: 已封存 badge and 封存備註 cell; on `/trip` it is no longer current, and it is under 已封存 (collapsed) with the remark's first line.
  4. ⋯ → 取消封存: back in 其他行程 / current, remark kept.
  Note what was checked in the commit message body. If the dev stack cannot start, say so rather than claiming this step.

**Leave the dev server's migration in place only while on this branch** — before switching branches, `venv/Scripts/python.exe -m alembic downgrade t2rip0000002`.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/pages/Trip.jsx
git commit -m "feat: archive, template and copy-from-template on the trip page" -- frontend/src/pages/Trip.jsx
```

---

### Task 6: Docs, and retiring the spec and plan

**Files:**
- Modify: `docs/data-model.md` (`trip` table section)
- Modify: `docs/business-rules.md` ("The current trip"; new "Archiving a trip", "Copying a trip")
- Modify: `docs/api.md` (Trips table)
- Modify: `docs/frontend.md` ("This time")
- Modify: `docs/notes/decisions.md` (a short subsection)
- Delete: `docs/superpowers/specs/2026-10-01-trip-archive-templates-design.md`, `docs/superpowers/plans/2026-10-01-trip-archive-templates.md`

Write present-tense, describing what is true now. Grep for each claim you change (`grep -n "current" docs/*.md`, `grep -n "其他行程" docs/*.md`) so a second copy is not left stating the old thing.

- [ ] **Step 1: `data-model.md`** — in the `trip` table, add rows after `notes`:

```markdown
| `archived` | boolean | no | `false` | Out of 其他行程 and never current. Undone by clearing it; locks nothing. |
| `archive_note` | text | yes | | 封存備註 — the remark written afterwards, separate from `notes`. Kept when the trip is un-archived. |
| `template` | boolean | no | `false` | Offered as a starting point for a new trip. Never current. Independent of `archived`. |
```

and update the section's lead to say a trip can be archived and can be a template.

- [ ] **Step 2: `business-rules.md`** — in "The current trip", first paragraph, add: "Archived trips and templates are never current; they are left out before the rule runs." Add after that section:

```markdown
## Archiving a trip

Archiving sets `archived` and nothing else. It does not check that the trip is
over — a cancelled trip can be archived — and it locks nothing: an archived
trip and its legs stay editable. Un-archiving clears the flag and leaves
`archive_note` as it was.

## Copying a trip

A new trip may be copied from any trip; the page offers templates. **The
definition carries; the state resets**, as with a packing list.

| Carries | Resets |
| --- | --- |
| trip `notes` (unless the request sends its own); each leg's `from_place`, `to_place`, `service`, `service_number`, `price`, `ticket_type`, `notes`, and its times, shifted | `booked`, `paid`, `collected` → `false`; `booking_code`, `seat`, `packing_list_id` → null |

The source's own `archived`, `archive_note`, `template` and `visibility` are
not copied.

**The shift.** `start_date` is a Taipei calendar day. Every leg moves by the
whole days between it and the Taipei day of the source's earliest departure,
so clock times and the gaps between legs survive; Taiwan keeps no daylight
saving. The shift may be negative. A source with no legs needs no date.

**Packing lists are not carried.** A list is linked from at most one leg, so a
copy cannot share them. The create response's `unlinked_from` names each source
leg that had one, and the page tells you to link a list yourself.
```

Also update the opening paragraph that lists where rules live (`trip.py` holds the current-trip rule) to say it holds the copy rule too.

- [ ] **Step 3: `api.md`** — in the Trips table, change the `POST /api/trips` and `PATCH` rows:

```markdown
| `POST` | `/api/trips` | none | `201`. `name` is required and non-empty. Optional `copy_from_id` copies another trip (see `business-rules.md`, "Copying a trip"): `404` `Trip to copy from not found.` for an unknown one, and `422` `start_date is required to copy a trip with legs.` when it has legs and no `start_date` (a date) was sent. Nothing is written on either refusal. The response adds `unlinked_from`: `[{from_place, to_place, packing_list_name}]`, empty unless a copied leg had a list. |
| `GET` / `PATCH` / `DELETE` | `/api/trips/{id}` | none | `404` when missing. `PATCH` takes `name`, `notes`, `archived`, `archive_note`, `template`; `name`, `archived` and `template` refuse null with `422`. Deleting takes the legs with it. |
```

and note in the `GET /api/trips` row that every trip carries `archived`, `archive_note` and `template`.

- [ ] **Step 4: `frontend.md`** — in "This time": replace the **其他行程** bullet with the three sections (其他行程 = neither archived nor template; 範本; 已封存 collapsed with each remark's first line), add a bullet for the ⋯ menu (封存 with its dialog, 取消封存, 設為範本/取消範本, 刪除行程) and the badges and 封存備註 cell, a bullet for 從範本 / 出發日期 on + 新增行程 and the notice after a copy (carried in the navigation state, so a reload drops it), and change the no-trip bullet's text to 還沒有進行中的行程。 with the sections below it.

- [ ] **Step 5: `notes/decisions.md`** — append under "Decisions for this application":

```markdown
### Archived and template trips are flags, and a copy does not take the lists

A trip's `archived` and `template` are booleans on `trip`, the way `saved` and
`template` are on `packing_list`, rather than a separate template table: a
template *is* a trip, edited on the same page. `archive_note` is separate from
`notes` because one is written before the trip and the other after.

Copying a trip shifts its legs by whole Taipei days to a chosen start date,
the same idea as the sheet import's `--trip-start`. Copying the linked packing
lists as well was considered and declined: the owner links lists by hand, so
the copy reports which legs had one instead.

Archiving is manual. Archiving automatically once the last leg ended was
considered and not wanted.
```

- [ ] **Step 6: Delete the spec and plan, commit**

```bash
git rm -q docs/superpowers/specs/2026-10-01-trip-archive-templates-design.md docs/superpowers/plans/2026-10-01-trip-archive-templates.md
git add docs/data-model.md docs/business-rules.md docs/api.md docs/frontend.md docs/notes/decisions.md
git commit -m "docs: trip archive and templates, and retire their spec and plan" -- docs/data-model.md docs/business-rules.md docs/api.md docs/frontend.md docs/notes/decisions.md docs/superpowers/specs/2026-10-01-trip-archive-templates-design.md docs/superpowers/plans/2026-10-01-trip-archive-templates.md
```

- [ ] **Step 7: Final full check**

Run pytest `-q`; `venv/Scripts/ruff.exe check .`; `cd frontend && npm run lint && npm test && npm run build`.
Expected: all green. Then push the branch and open the PR into `dev` (the main session does that).
