"""Trips and their legs, and the four shelves they sit on."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.constants import Kind, LabelKind, Usage
from app.database import get_db
from app.models import PackingList, Trip, TripLeg
from app.schemas.trip import (
    ARRIVAL_BEFORE_DEPARTURE,
    TripCreate,
    TripCreated,
    TripIds,
    TripIndex,
    TripLegBase,
    TripLegResponse,
    TripLegUpdate,
    TripResponse,
    TripUpdate,
)
from app.services.domain.auto_save import (
    AUTO_SAVE_LIMIT,
    AutoSaveFull,
    KindRefused,
    apply_kind,
    evict_next,
)
from app.services.domain.labels import remember_label
from app.services.domain.trip import copy_legs

router = APIRouter(tags=["Trips"])

TRIP_NOT_FOUND = "Trip not found."
LEG_NOT_FOUND = "Trip leg not found."
LIST_NOT_FOUND = "Packing list not found."
LIST_ALREADY_LINKED = "That packing list is already linked to another leg."
COPY_SOURCE_NOT_FOUND = "Trip to copy from not found."
START_DATE_REQUIRED = "start_date is required to copy a trip with legs."

def _trips_query():
    return select(Trip).options(selectinload(Trip.legs).selectinload(TripLeg.packing_list))


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


# --- trips ------------------------------------------------------------------


def _refusal(slot: list[Trip]) -> str:
    """A plain string naming what would go; the ids come from `evict_next`."""
    names = " and ".join(f'"{trip.name}"' for trip in slot)
    return (
        f"Auto-save already holds {AUTO_SAVE_LIMIT[Trip]} trips. Marking this one past would delete "
        f"{names}, the oldest. Save it first if you want to keep it, or confirm "
        f"to replace it."
    )


@router.get("/api/trips", response_model=TripIndex)
def list_trips(db: Session = Depends(get_db)):
    trips = db.scalars(_trips_query()).all()
    # Newest created first, the same order as packing lists.
    ordered = sorted(trips, key=lambda trip: (trip.created_at, trip.id), reverse=True)
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


@router.get("/api/trips/{trip_id}", response_model=TripResponse)
def read_trip(trip_id: int, db: Session = Depends(get_db)):
    return _get_trip(db, trip_id)


@router.patch("/api/trips/{trip_id}", response_model=TripResponse)
def update_trip(trip_id: int, payload: TripUpdate, db: Session = Depends(get_db)):
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


@router.delete("/api/trips/{trip_id}", status_code=204)
def delete_trip(trip_id: int, db: Session = Depends(get_db)):
    db.delete(_get_trip(db, trip_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- legs -------------------------------------------------------------------


@router.post("/api/trips/{trip_id}/legs", response_model=TripLegResponse, status_code=201)
def create_leg(trip_id: int, payload: TripLegBase, db: Session = Depends(get_db)):
    if db.get(Trip, trip_id) is None:
        raise HTTPException(status_code=404, detail=TRIP_NOT_FOUND)
    _check_link(db, payload.packing_list_id)
    leg = TripLeg(trip_id=trip_id, **payload.model_dump())
    db.add(leg)
    remember_label(db, LabelKind.TICKET_TYPE, leg.ticket_type)
    _commit(db)
    db.refresh(leg)
    return leg


@router.patch("/api/trip-legs/{leg_id}", response_model=TripLegResponse)
def update_leg(leg_id: int, payload: TripLegUpdate, db: Session = Depends(get_db)):
    leg = _get_leg(db, leg_id)
    changes = payload.model_dump(exclude_unset=True)
    departs = changes.get("departs_at", leg.departs_at)
    arrives = changes.get("arrives_at", leg.arrives_at)
    if arrives <= departs:
        raise HTTPException(status_code=422, detail=ARRIVAL_BEFORE_DEPARTURE)
    _check_link(db, changes.get("packing_list_id"), excluding=leg.id)
    for field, value in changes.items():
        setattr(leg, field, value)
    remember_label(db, LabelKind.TICKET_TYPE, leg.ticket_type)
    _commit(db)
    db.refresh(leg)
    return leg


@router.delete("/api/trip-legs/{leg_id}", status_code=204)
def delete_leg(leg_id: int, db: Session = Depends(get_db)):
    db.delete(_get_leg(db, leg_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
