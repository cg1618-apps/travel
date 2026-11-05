"""Trips and their legs, the four shelves they sit on, and the 自動保存 queue.

Which moves between kinds are allowed and what fills or drops a 自動保存 slot
live in `app.services.domain.auto_save`; this router only translates its
refusals into 422 and 409.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.constants import Kind, LabelKind, Usage
from app.database import get_db
from app.models import PackingList, Trip, TripLeg
from app.schemas.trip import (
    TripBackupResponse,
    TripCreate,
    TripCreated,
    TripIds,
    TripIndex,
    TripLegCreate,
    TripLegResponse,
    TripLegUpdate,
    TripResponse,
    TripUpdate,
    arrival_refusal,
    fill_arrival,
)
from app.services.domain.auto_save import (
    AUTO_SAVE_LIMIT,
    AutoSaveFull,
    KindRefused,
    apply_kind,
    evict_next,
)
from app.services.domain.labels import remember_label
from app.services.domain.leg_types import (
    FLAGS,
    default_flags,
    flag_refusals,
    ride_type_refusal,
)
from app.services.domain.trip import (
    RoundTripRefused,
    apply_round_trip,
    copy_legs,
    is_ready,
    needs_start_date,
    not_ready_message,
    section_for,
    settle_done,
)

router = APIRouter(tags=["Trips"])

TRIP_NOT_FOUND = "Trip not found."
LEG_NOT_FOUND = "Trip leg not found."
LIST_NOT_FOUND = "Packing list not found."
LIST_ALREADY_LINKED = "That packing list is already linked to another leg."
COPY_SOURCE_NOT_FOUND = "Trip to copy from not found."
START_DATE_REQUIRED = "start_date is required to copy a trip with legs."
BACKUP_OF_A_BACKUP = "A backup cannot have backups of its own."
BACKUP_WITH_A_LIST = "A backup cannot link a packing list."


def _trips_query():
    legs = selectinload(Trip.legs)
    return select(Trip).options(
        legs.selectinload(TripLeg.packing_list), legs.selectinload(TripLeg.backups)
    )


def _get_trip(db: Session, trip_id: int) -> Trip:
    trip = db.scalars(_trips_query().where(Trip.id == trip_id)).first()
    if trip is None:
        raise HTTPException(status_code=404, detail=TRIP_NOT_FOUND)
    return trip


def _get_leg(db: Session, leg_id: int) -> TripLeg:
    leg = db.get(TripLeg, leg_id)
    if leg is None:
        raise HTTPException(status_code=404, detail=LEG_NOT_FOUND)
    return leg


def _check_link(db: Session, packing_list_id: int | None, *, excluding: int | None = None) -> None:
    """404 for a list that does not exist, 409 for one another leg already holds.

    The check gives the refusal its message; the unique constraint is what holds
    under a race, and `_commit` turns that into the same 409. `excluding` is the
    leg being edited, so keeping its own link is not a collision with itself.
    """
    if packing_list_id is None:
        return
    if db.get(PackingList, packing_list_id) is None:
        raise HTTPException(status_code=404, detail=LIST_NOT_FOUND)
    query = select(TripLeg.id).where(TripLeg.packing_list_id == packing_list_id)
    if excluding is not None:
        query = query.where(TripLeg.id != excluding)
    if db.execute(query).first() is not None:
        raise HTTPException(status_code=409, detail=LIST_ALREADY_LINKED)


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=LIST_ALREADY_LINKED) from None


def _refusal(slot: list[Trip]) -> str:
    """A plain string naming what would go; the ids come from `evict_next`."""
    names = " and ".join(f'"{trip.name}"' for trip in slot)
    return (
        f"Auto-save already holds {AUTO_SAVE_LIMIT[Trip]} trips. Marking this one "
        f"past would delete {names}, the oldest. Save it first if you want to keep "
        f"it, or confirm to replace it."
    )


def _responses(trips) -> list[TripResponse]:
    return [TripResponse.model_validate(trip) for trip in trips]


# --- trips ------------------------------------------------------------------


@router.get("/api/trips", response_model=TripIndex)
def list_trips(db: Session = Depends(get_db)):
    # Newest created first, the same order as packing lists. Every trip is on
    # exactly one shelf: `kind` is one value, and 自動保存 is the 一般 trips
    # whose usage is past.
    trips = db.scalars(_trips_query().order_by(Trip.created_at.desc(), Trip.id.desc())).all()
    auto_saved = sorted(
        (trip for trip in trips if trip.kind == Kind.FREE and trip.usage == Usage.PAST),
        key=lambda trip: (trip.auto_saved_at, trip.id),
        reverse=True,
    )
    return TripIndex(
        free=_responses(t for t in trips if t.kind == Kind.FREE and t.usage != Usage.PAST),
        auto_saved=_responses(auto_saved),
        saved=_responses(t for t in trips if t.kind == Kind.SAVED),
        templates=_responses(t for t in trips if t.kind == Kind.TEMPLATE),
        evict_next=_responses(evict_next(db, Trip)),
    )


@router.post("/api/trips/bulk-delete", status_code=204)
def bulk_delete_trips(payload: TripIds, db: Session = Depends(get_db)):
    """All or nothing: one missing id refuses the whole request.

    Legs go by cascade; a linked packing list is kept and unlinked, as on any
    trip delete.
    """
    ids = set(payload.ids)
    trips = db.scalars(select(Trip).where(Trip.id.in_(ids))).all() if ids else []
    if len(trips) != len(ids):
        raise HTTPException(status_code=404, detail=TRIP_NOT_FOUND)
    for trip in trips:
        db.delete(trip)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/api/trips", response_model=TripCreated, status_code=201)
def create_trip(payload: TripCreate, db: Session = Depends(get_db)):
    source = None
    if payload.copy_from_id is not None:
        # Both refusals come before anything is written.
        source = db.scalars(_trips_query().where(Trip.id == payload.copy_from_id)).first()
        if source is None:
            raise HTTPException(status_code=404, detail=COPY_SOURCE_NOT_FOUND)
        if needs_start_date(source) and payload.start_date is None:
            raise HTTPException(status_code=422, detail=START_DATE_REQUIRED)

    trip = Trip(**payload.model_dump(exclude={"copy_from_id", "start_date"}))
    if source is not None:
        if "notes" not in payload.model_fields_set:
            trip.notes = source.notes
        # The shape carries, so the copied legs' sections still mean something;
        # `ticket_status` and `done` are state and start over.
        trip.round_trip = source.round_trip
        trip.outbound_title = source.outbound_title
        trip.outbound_notes = source.outbound_notes
        trip.return_title = source.return_title
        trip.return_notes = source.return_notes
    db.add(trip)
    db.flush()

    unlinked = copy_legs(db, source, trip, payload.start_date) if source is not None else []
    db.commit()
    created = TripResponse.model_validate(_get_trip(db, trip.id))
    return TripCreated(**created.model_dump(), unlinked_from=unlinked)


@router.get("/api/trips/{trip_id}", response_model=TripResponse)
def read_trip(trip_id: int, db: Session = Depends(get_db)):
    return _get_trip(db, trip_id)


@router.patch("/api/trips/{trip_id}", response_model=TripResponse)
def update_trip(trip_id: int, payload: TripUpdate, db: Session = Depends(get_db)):
    trip = _get_trip(db, trip_id)
    changes = payload.model_dump(exclude_unset=True, exclude={"evict_confirmed"})
    try:
        apply_kind(
            db, trip, changes, confirmed=payload.evict_confirmed, now=datetime.now(timezone.utc)
        )
    except KindRefused as refused:
        raise HTTPException(status_code=422, detail=str(refused)) from None
    except AutoSaveFull as full:
        raise HTTPException(status_code=409, detail=_refusal(full.slot)) from None
    if "round_trip" in changes:
        try:
            apply_round_trip(
                trip,
                changes.pop("round_trip"),
                return_title=changes.get("return_title", trip.return_title),
                return_notes=changes.get("return_notes", trip.return_notes),
            )
        except RoundTripRefused as refused:
            db.rollback()
            raise HTTPException(status_code=422, detail=str(refused)) from None
    done = changes.pop("done", None)
    for field, value in changes.items():
        setattr(trip, field, value)
    # Judged on the trip as this request leaves it, so a body that settles the
    # tickets and marks the trip done in one go is allowed.
    if done is True and not is_ready(trip):
        db.rollback()
        raise HTTPException(status_code=422, detail=not_ready_message(trip))
    if done is not None:
        trip.done = done
    settle_done(db, trip)
    db.commit()
    db.expire_all()
    return _get_trip(db, trip_id)


@router.delete("/api/trips/{trip_id}", status_code=204)
def delete_trip(trip_id: int, db: Session = Depends(get_db)):
    db.delete(_get_trip(db, trip_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- legs -------------------------------------------------------------------


@router.post("/api/trips/{trip_id}/legs", response_model=TripLegResponse, status_code=201)
def create_leg(trip_id: int, payload: TripLegCreate, db: Session = Depends(get_db)):
    trip = db.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail=TRIP_NOT_FOUND)
    _check_link(db, payload.packing_list_id)
    fields = payload.model_dump()
    fields["section"] = section_for(trip, payload.section)
    leg = TripLeg(trip_id=trip_id, **fields)
    db.add(leg)
    remember_label(db, LabelKind.TICKET_TYPE, leg.ticket_type)
    settle_done(db, trip)
    _commit(db)
    db.refresh(leg)
    return leg


@router.post("/api/trip-legs/{leg_id}/backups", response_model=TripBackupResponse, status_code=201)
def create_backup(leg_id: int, payload: TripLegCreate, db: Session = Depends(get_db)):
    """A 備案 of an entry: the same fields, added under it. Nothing about the
    trip's readiness can change, so `done` is left alone."""
    leg = _get_leg(db, leg_id)
    if leg.backup_of_id is not None:
        raise HTTPException(status_code=422, detail=BACKUP_OF_A_BACKUP)
    if payload.packing_list_id is not None:
        raise HTTPException(status_code=422, detail=BACKUP_WITH_A_LIST)
    # A backup has no section of its own, whatever was sent, as a one-way
    # trip's entry has none.
    fields = payload.model_dump(exclude={"section"})
    backup = TripLeg(trip_id=leg.trip_id, backup_of_id=leg.id, **fields)
    db.add(backup)
    remember_label(db, LabelKind.TICKET_TYPE, backup.ticket_type)
    db.commit()
    db.refresh(backup)
    return backup


def _leg_refusals(leg: TripLeg, changes: dict) -> list[str]:
    """Why the leg as this PATCH would leave it cannot be stored.

    Fills `changes` as it goes: the arrival from the departure, and, when the
    type changes, every switch the body does not name from the new type's
    defaults.
    """
    departs = changes.get("departs_at", leg.departs_at)
    arrives = changes.get("arrives_at", leg.arrives_at)
    filled = fill_arrival(departs, arrives)
    if filled is not arrives:
        changes["arrives_at"] = filled
    refusals = [r for r in [arrival_refusal(departs, filled)] if r]

    transport_type = changes.get("transport_type", leg.transport_type)
    if transport_type != leg.transport_type:
        for flag, value in default_flags(transport_type).items():
            changes.setdefault(flag, value)
    refusals += flag_refusals(transport_type, {f: changes[f] for f in FLAGS if f in changes})
    # Only a ride type sent is judged: one kept from an earlier type is not
    # shown, and switching back brings it back.
    if "ride_type" in changes:
        ride = ride_type_refusal(transport_type, changes["ride_type"])
        if ride:
            refusals.append(ride)
    if leg.backup_of_id is not None and changes.get("packing_list_id") is not None:
        refusals.append(BACKUP_WITH_A_LIST)
    return refusals


@router.patch("/api/trip-legs/{leg_id}", response_model=TripLegResponse)
def update_leg(leg_id: int, payload: TripLegUpdate, db: Session = Depends(get_db)):
    leg = _get_leg(db, leg_id)
    changes = payload.model_dump(exclude_unset=True)
    refusals = _leg_refusals(leg, changes)
    if refusals:
        raise HTTPException(status_code=422, detail=" ".join(refusals))
    _check_link(db, changes.get("packing_list_id"), excluding=leg.id)
    if "section" in changes:
        changes["section"] = (
            None if leg.backup_of_id is not None else section_for(leg.trip, changes["section"])
        )
    for field, value in changes.items():
        setattr(leg, field, value)
    remember_label(db, LabelKind.TICKET_TYPE, leg.ticket_type)
    settle_done(db, leg.trip)
    _commit(db)
    db.refresh(leg)
    return leg


@router.delete("/api/trip-legs/{leg_id}", status_code=204)
def delete_leg(leg_id: int, db: Session = Depends(get_db)):
    db.delete(_get_leg(db, leg_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
