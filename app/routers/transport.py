"""Transport: routes, the options and notes on them, and the departures of
each option.

Item-style paths, like packing items: a child is created under its parent and
addressed on its own afterwards, so the paths are written out in full rather
than hung off one router prefix. Two whole-order writes set every route's
position, and every option's on one route, as `PUT /api/packing-lists/{id}/order`
does for items.
"""

from datetime import time as clock_time

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import (
    TransportDeparture,
    TransportNote,
    TransportNoteLink,
    TransportOption,
    TransportRoute,
)
from app.schemas.transport import (
    NOTE_NEEDS_TITLE_OR_LINK,
    TransportDepartureCreate,
    TransportDepartureResponse,
    TransportDepartureUpdate,
    TransportNoteCreate,
    TransportNoteOrder,
    TransportNoteResponse,
    TransportNoteUpdate,
    TransportOptionBase,
    TransportOptionOrder,
    TransportOptionResponse,
    TransportOptionUpdate,
    TransportRouteBase,
    TransportRouteOrder,
    TransportRouteResponse,
    TransportRouteUpdate,
)
from app.services.domain.ordering import (
    OrderRefused,
    apply_order,
    check_groups,
    check_order,
    place_in_group,
    ungrouped_or_named,
)

router = APIRouter(tags=["Transport"])

ROUTE_NOT_FOUND = "Transport route not found."
OPTION_NOT_FOUND = "Transport option not found."
DEPARTURE_NOT_FOUND = "Transport departure not found."
NOTE_NOT_FOUND = "Transport note not found."
DUPLICATE_DEPARTURE = "That departure already exists for this option."


def _routes_query():
    return select(TransportRoute).options(
        selectinload(TransportRoute.options).selectinload(TransportOption.departures),
        selectinload(TransportRoute.note_entries).selectinload(TransportNote.links),
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


def _get_note(db: Session, note_id: int) -> TransportNote:
    note = db.scalars(
        select(TransportNote)
        .where(TransportNote.id == note_id)
        .options(selectinload(TransportNote.links))
    ).first()
    if note is None:
        raise HTTPException(status_code=404, detail=NOTE_NOT_FOUND)
    return note


#: Every route is in one set: no scope narrows it.
ALL_ROUTES: dict = {}


def _next_option_position(db: Session, route_id: int) -> int:
    """One past the end of THIS route, for the same reason items are per list."""
    highest = db.execute(
        select(func.max(TransportOption.position)).where(TransportOption.route_id == route_id)
    ).scalar()
    return 0 if highest is None else highest + 1


def _next_note_position(db: Session, route_id: int) -> int:
    highest = db.execute(
        select(func.max(TransportNote.position)).where(TransportNote.route_id == route_id)
    ).scalar()
    return 0 if highest is None else highest + 1


def _link_rows(urls: list[str]) -> list[TransportNoteLink]:
    return [TransportNoteLink(url=url, position=position) for position, url in enumerate(urls)]


def _apply_order(
    rows: dict, ids: list[int], *, noun: str, where: str, groups: dict | None = None
) -> None:
    """Check the whole order, and that it splits no group when `groups` maps
    each row to its group; then apply it."""
    try:
        check_order(ids, rows, noun=noun, where=where)
        if groups is not None:
            check_groups(ids, groups, noun=noun, describe=ungrouped_or_named)
    except OrderRefused as refused:
        raise HTTPException(status_code=422, detail=str(refused)) from None
    apply_order(rows, ids)


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


@router.put("/api/transport-routes/order", response_model=list[TransportRouteResponse])
def reorder_routes(payload: TransportRouteOrder, db: Session = Depends(get_db)):
    """Every route's position in one write. A literal path, declared before
    the `{route_id}` routes, so "order" is never read as an id."""
    routes = {route.id: route for route in db.scalars(select(TransportRoute))}
    _apply_order(
        routes,
        payload.route_ids,
        noun="route",
        where="among the routes",
        groups={route_id: route.group_name for route_id, route in routes.items()},
    )
    db.commit()
    db.expire_all()
    return list_routes(db)


@router.post("/api/transport-routes", response_model=TransportRouteResponse, status_code=201)
def create_route(payload: TransportRouteBase, db: Session = Depends(get_db)):
    position = place_in_group(db, TransportRoute, ALL_ROUTES, "group_name", payload.group_name)
    route = TransportRoute(position=position, **payload.model_dump())
    db.add(route)
    db.commit()
    return _get_route(db, route.id)


@router.get("/api/transport-routes/{route_id}", response_model=TransportRouteResponse)
def read_route(route_id: int, db: Session = Depends(get_db)):
    return _get_route(db, route_id)


@router.patch("/api/transport-routes/{route_id}", response_model=TransportRouteResponse)
def update_route(route_id: int, payload: TransportRouteUpdate, db: Session = Depends(get_db)):
    route = _get_route(db, route_id)
    changes = payload.model_dump(exclude_unset=True)
    moved = "group_name" in changes and changes["group_name"] != route.group_name
    for field, value in changes.items():
        setattr(route, field, value)
    # A new group: the route joins the end of it, as an item does on a new
    # category. A position sent in the same PATCH is taken as meant and wins.
    if moved and "position" not in changes:
        route.position = place_in_group(
            db, TransportRoute, ALL_ROUTES, "group_name", route.group_name, exclude_id=route.id
        )
    db.commit()
    db.expire_all()
    return _get_route(db, route_id)


@router.delete("/api/transport-routes/{route_id}", status_code=204)
def delete_route(route_id: int, db: Session = Depends(get_db)):
    db.delete(_get_route(db, route_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/api/transport-routes/{route_id}/order", response_model=TransportRouteResponse)
def reorder_options(route_id: int, payload: TransportOptionOrder, db: Session = Depends(get_db)):
    """Every option's position on this route in one write; an option of
    another route is foreign here, as an item of another list is."""
    route = _get_route(db, route_id)
    options = {option.id: option for option in route.options}
    _apply_order(options, payload.option_ids, noun="option", where="on this route")
    db.commit()
    db.expire_all()
    return _get_route(db, route_id)


@router.put("/api/transport-routes/{route_id}/note-order", response_model=TransportRouteResponse)
def reorder_notes(route_id: int, payload: TransportNoteOrder, db: Session = Depends(get_db)):
    """Every note's position on this route in one write; a note of another
    route is foreign here."""
    route = _get_route(db, route_id)
    notes = {note.id: note for note in route.note_entries}
    _apply_order(notes, payload.note_ids, noun="note", where="on this route")
    db.commit()
    db.expire_all()
    return _get_route(db, route_id)


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


# --- notes ------------------------------------------------------------------


@router.post(
    "/api/transport-routes/{route_id}/notes",
    response_model=TransportNoteResponse,
    status_code=201,
)
def create_note(route_id: int, payload: TransportNoteCreate, db: Session = Depends(get_db)):
    if db.get(TransportRoute, route_id) is None:
        raise HTTPException(status_code=404, detail=ROUTE_NOT_FOUND)
    note = TransportNote(
        route_id=route_id,
        title=payload.title,
        description=payload.description,
        position=_next_note_position(db, route_id),
        links=_link_rows(payload.links),
    )
    db.add(note)
    db.commit()
    db.expire_all()
    return _get_note(db, note.id)


@router.patch("/api/transport-notes/{note_id}", response_model=TransportNoteResponse)
def update_note(note_id: int, payload: TransportNoteUpdate, db: Session = Depends(get_db)):
    note = _get_note(db, note_id)
    changes = payload.model_dump(exclude_unset=True)
    # The title-or-link rule holds for the note as it will be, not the body:
    # a body clearing the title is fine while the note keeps a link.
    title = changes.get("title", note.title)
    links = changes["links"] if "links" in changes else [link.url for link in note.links]
    if title is None and not links:
        raise HTTPException(status_code=422, detail=NOTE_NEEDS_TITLE_OR_LINK)
    if "links" in changes:
        # Replaced, not merged: delete-orphan removes the old rows.
        note.links = _link_rows(changes.pop("links"))
    for field, value in changes.items():
        setattr(note, field, value)
    db.commit()
    db.expire_all()
    return _get_note(db, note_id)


@router.delete("/api/transport-notes/{note_id}", status_code=204)
def delete_note(note_id: int, db: Session = Depends(get_db)):
    db.delete(_get_note(db, note_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
