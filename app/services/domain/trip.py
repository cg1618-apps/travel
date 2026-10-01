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
