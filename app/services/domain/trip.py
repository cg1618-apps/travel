"""Which trip is current, and what a copied trip carries."""

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.constants import TAIPEI, Kind, Usage
from app.models import Trip, TripLeg


def current_trip(db: Session, now: datetime) -> Trip | None:
    """The 使用中 trip; with none, the 未來使用 one. Within a group, the trip
    whose soonest leg still ahead is earliest; trips with nothing ahead come
    after, newest (highest id) first, and so does a tie. A trip with no legs
    can be current - its status, not its legs, says it is the one being taken.

    Computed in Python over the candidates: there are a handful, and the rule
    reads more plainly here than as SQL.
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

    def rank(trip: Trip) -> tuple:
        ahead = [leg.departs_at for leg in trip.legs if leg.departs_at > now]
        if ahead:
            return (0, min(ahead), -trip.id)
        return (1, now, -trip.id)

    for usage in (Usage.IN_USE, Usage.UPCOMING):
        group = [trip for trip in trips if trip.usage == usage]
        if group:
            return min(group, key=rank)
    return None


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
