"""What a copied trip carries."""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.constants import TAIPEI
from app.models import Trip, TripLeg


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
