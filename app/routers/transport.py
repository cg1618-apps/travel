"""Transport: routes, the options on them, and the departures of each option.

Item-style paths, like packing items: a child is created under its parent and
addressed on its own afterwards, so the paths are written out in full rather
than hung off one router prefix.
"""

from datetime import time as clock_time

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import TransportDeparture, TransportOption, TransportRoute
from app.schemas.transport import (
    TransportDepartureCreate,
    TransportDepartureResponse,
    TransportDepartureUpdate,
    TransportOptionBase,
    TransportOptionResponse,
    TransportOptionUpdate,
    TransportRouteBase,
    TransportRouteResponse,
    TransportRouteUpdate,
)

router = APIRouter(tags=["Transport"])

ROUTE_NOT_FOUND = "Transport route not found."
OPTION_NOT_FOUND = "Transport option not found."
DEPARTURE_NOT_FOUND = "Transport departure not found."
DUPLICATE_DEPARTURE = "That departure already exists for this option."


def _routes_query():
    return select(TransportRoute).options(
        selectinload(TransportRoute.options).selectinload(TransportOption.departures)
    )


def _get_route(db: Session, route_id: int) -> TransportRoute:
    route = db.scalars(_routes_query().where(TransportRoute.id == route_id)).first()
    if route is None:
        raise HTTPException(status_code=404, detail=ROUTE_NOT_FOUND)
    return route


def _get_option(db: Session, option_id: int) -> TransportOption:
    option = db.get(TransportOption, option_id)
    if option is None:
        raise HTTPException(status_code=404, detail=OPTION_NOT_FOUND)
    return option


def _get_departure(db: Session, departure_id: int) -> TransportDeparture:
    departure = db.get(TransportDeparture, departure_id)
    if departure is None:
        raise HTTPException(status_code=404, detail=DEPARTURE_NOT_FOUND)
    return departure


def _next_route_position(db: Session) -> int:
    highest = db.execute(select(func.max(TransportRoute.position))).scalar()
    return 0 if highest is None else highest + 1


def _next_option_position(db: Session, route_id: int) -> int:
    """One past the end of THIS route, for the same reason items are per list."""
    highest = db.execute(
        select(func.max(TransportOption.position)).where(TransportOption.route_id == route_id)
    ).scalar()
    return 0 if highest is None else highest + 1


def _refuse_duplicate(
    db: Session,
    option_id: int,
    day_type: str,
    time: clock_time,
    *,
    excluding: int | None = None,
) -> None:
    """409 when another departure already holds (option, day type, time).

    The check is what gives the refusal a message; the unique constraint is
    what holds under a race, and `_commit_departure` turns that into the same 409.
    """
    query = select(TransportDeparture.id).where(
        TransportDeparture.option_id == option_id,
        TransportDeparture.day_type == day_type,
        TransportDeparture.time == time,
    )
    if excluding is not None:
        query = query.where(TransportDeparture.id != excluding)
    if db.execute(query).first() is not None:
        raise HTTPException(status_code=409, detail=DUPLICATE_DEPARTURE)


def _commit_departure(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=DUPLICATE_DEPARTURE) from None


# --- routes -----------------------------------------------------------------


@router.get("/api/transport-routes", response_model=list[TransportRouteResponse])
def list_routes(db: Session = Depends(get_db)):
    query = _routes_query().order_by(TransportRoute.position, TransportRoute.id)
    return db.scalars(query).all()


@router.post("/api/transport-routes", response_model=TransportRouteResponse, status_code=201)
def create_route(payload: TransportRouteBase, db: Session = Depends(get_db)):
    route = TransportRoute(position=_next_route_position(db), **payload.model_dump())
    db.add(route)
    db.commit()
    return _get_route(db, route.id)


@router.get("/api/transport-routes/{route_id}", response_model=TransportRouteResponse)
def read_route(route_id: int, db: Session = Depends(get_db)):
    return _get_route(db, route_id)


@router.patch("/api/transport-routes/{route_id}", response_model=TransportRouteResponse)
def update_route(route_id: int, payload: TransportRouteUpdate, db: Session = Depends(get_db)):
    route = _get_route(db, route_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(route, field, value)
    db.commit()
    db.expire_all()
    return _get_route(db, route_id)


@router.delete("/api/transport-routes/{route_id}", status_code=204)
def delete_route(route_id: int, db: Session = Depends(get_db)):
    db.delete(_get_route(db, route_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- options ----------------------------------------------------------------


@router.post(
    "/api/transport-routes/{route_id}/options",
    response_model=TransportOptionResponse,
    status_code=201,
)
def create_option(route_id: int, payload: TransportOptionBase, db: Session = Depends(get_db)):
    if db.get(TransportRoute, route_id) is None:
        raise HTTPException(status_code=404, detail=ROUTE_NOT_FOUND)
    option = TransportOption(
        route_id=route_id, position=_next_option_position(db, route_id), **payload.model_dump()
    )
    db.add(option)
    db.commit()
    db.refresh(option)
    return option


@router.patch("/api/transport-options/{option_id}", response_model=TransportOptionResponse)
def update_option(option_id: int, payload: TransportOptionUpdate, db: Session = Depends(get_db)):
    option = _get_option(db, option_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(option, field, value)
    db.commit()
    db.refresh(option)
    return option


@router.delete("/api/transport-options/{option_id}", status_code=204)
def delete_option(option_id: int, db: Session = Depends(get_db)):
    db.delete(_get_option(db, option_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- departures -------------------------------------------------------------


@router.post(
    "/api/transport-options/{option_id}/departures",
    response_model=TransportDepartureResponse,
    status_code=201,
)
def create_departure(
    option_id: int, payload: TransportDepartureCreate, db: Session = Depends(get_db)
):
    _get_option(db, option_id)
    _refuse_duplicate(db, option_id, payload.day_type, payload.time)
    departure = TransportDeparture(option_id=option_id, **payload.model_dump())
    db.add(departure)
    _commit_departure(db)
    db.refresh(departure)
    return departure


@router.patch("/api/transport-departures/{departure_id}", response_model=TransportDepartureResponse)
def update_departure(
    departure_id: int, payload: TransportDepartureUpdate, db: Session = Depends(get_db)
):
    departure = _get_departure(db, departure_id)
    changes = payload.model_dump(exclude_unset=True)
    _refuse_duplicate(
        db,
        departure.option_id,
        changes.get("day_type", departure.day_type),
        changes.get("time", departure.time),
        excluding=departure.id,
    )
    for field, value in changes.items():
        setattr(departure, field, value)
    _commit_departure(db)
    db.refresh(departure)
    return departure


@router.delete("/api/transport-departures/{departure_id}", status_code=204)
def delete_departure(departure_id: int, db: Session = Depends(get_db)):
    db.delete(_get_departure(db, departure_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
