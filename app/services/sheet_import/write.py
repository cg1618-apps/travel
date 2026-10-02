"""Write a parsed sheet into the database, or refuse without writing anything.

The caller owns the transaction: this flushes and never commits, so a dry run
is a rollback.
"""

from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import LabelKind
from app.models import (
    PackingItem,
    PackingList,
    TransportDeparture,
    TransportOption,
    TransportRoute,
    Trip,
    TripLeg,
)
from app.services.domain.labels import remember_item_labels, remember_label
from app.services.sheet_import.parse import ParsedSheet


class ImportClash(Exception):
    """The database already holds something this import would create."""

    def __init__(self, clashes: list[str]):
        super().__init__("; ".join(clashes))
        self.clashes = clashes


def find_clashes(db: Session, sheet: ParsedSheet) -> list[str]:
    clashes = []
    for parsed in sheet.lists:
        if db.execute(select(PackingList.id).where(PackingList.name == parsed.name)).first():
            clashes.append(f"packing list {parsed.name} already exists")
    for route in sheet.routes:
        exists = db.execute(select(TransportRoute.id).where(
            TransportRoute.from_place == route.from_place, TransportRoute.to_place == route.to_place
        )).first()
        if exists:
            clashes.append(f"route {route.from_place} to {route.to_place} already exists")
    if db.execute(select(Trip.id).where(Trip.name == sheet.trip.name)).first():
        clashes.append(f"trip {sheet.trip.name} already exists")
    return clashes


def _write_list(db: Session, parsed) -> PackingList:
    row = PackingList(name=parsed.name, leg=parsed.leg, pair_id=parsed.pair_id)
    db.add(row)
    for position, parsed_item in enumerate(parsed.items):
        item = PackingItem(position=position, **asdict(parsed_item))
        row.items.append(item)
        remember_item_labels(db, item)
    return row


def _write_route(db: Session, position: int, parsed) -> None:
    route = TransportRoute(
        from_place=parsed.from_place, to_place=parsed.to_place, notes=parsed.notes, position=position
    )
    db.add(route)
    for option_position, parsed_option in enumerate(parsed.options):
        fields = asdict(parsed_option)
        departures = fields.pop("departures")
        option = TransportOption(position=option_position, **fields)
        option.departures = [TransportDeparture(**d) for d in departures]
        route.options.append(option)


def _write_trip(db: Session, sheet: ParsedSheet, lists: dict[str, PackingList]) -> None:
    trip = Trip(name=sheet.trip.name)
    db.add(trip)
    for parsed in sheet.trip.legs:
        fields = asdict(parsed)
        list_name = fields.pop("packing_list_name")
        leg = TripLeg(packing_list=lists.get(list_name), **fields)
        trip.legs.append(leg)
        remember_label(db, LabelKind.TICKET_TYPE, parsed.ticket_type)


def write_sheet(db: Session, sheet: ParsedSheet) -> None:
    clashes = find_clashes(db, sheet)
    if clashes:
        raise ImportClash(clashes)
    lists = {parsed.name: _write_list(db, parsed) for parsed in sheet.lists}
    for position, route in enumerate(sheet.routes):
        _write_route(db, position, route)
    _write_trip(db, sheet, lists)
    db.flush()
