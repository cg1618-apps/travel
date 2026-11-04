"""The rules about a trip's contents: what a copy carries, when a trip is
ready, what a round trip keeps in its sections.

Nothing here raises `HTTPException`. The router decides what a refusal looks
like over HTTP; these functions only answer questions and perform changes.
"""

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.constants import TAIPEI, Leg, TicketStatus
from app.models import Trip, TripLeg
from app.services.domain.leg_types import unticked_labels


def earliest_departure(trip: Trip) -> datetime | None:
    """The trip's start: its earliest entry departure, or None when no entry
    has one."""
    times = [leg.departs_at for leg in trip.legs if leg.departs_at is not None]
    return min(times) if times else None


# --- readiness ------------------------------------------------------------------


def not_ready_reasons(trip: Trip) -> list[str]:
    """What keeps the trip from 已準備完成, in English; empty when it is ready.

    Ready is: tickets bought or not needed, and every label each entry shows
    ticked. A label an entry's type lacks, or whose switch is off, does not
    count; nor does the booking code, which is a field and not a label.
    """
    reasons = []
    if trip.ticket_status == TicketStatus.NOT_BOUGHT:
        reasons.append("tickets not bought")
    unticked = sum(1 for leg in trip.legs if unticked_labels(leg))
    if unticked:
        reasons.append(
            f"{unticked} {'entry has' if unticked == 1 else 'entries have'} unticked labels"
        )
    return reasons


def is_ready(trip: Trip) -> bool:
    return not not_ready_reasons(trip)


def not_ready_message(trip: Trip) -> str:
    return f"The trip is not ready: {'; '.join(not_ready_reasons(trip))}."


def settle_done(db: Session, trip: Trip) -> None:
    """Clear `done` on a trip that is no longer ready.

    Called after every write that can make a trip less ready - a leg created
    or changed, `ticket_status` moved - in the same transaction, so a done
    trip is never stored not ready. Never sets `done`: that is the owner's.
    """
    db.flush()
    db.refresh(trip, ["legs"])
    if trip.done and not is_ready(trip):
        trip.done = False


# --- round trips ----------------------------------------------------------------


class RoundTripRefused(ValueError):
    """Switching to one-way would hide something. The message is the 422's."""


def section_for(trip: Trip, section: str | None) -> str | None:
    """The section an entry of this trip is stored in: null on a one-way
    trip whatever was sent, 去程 on a round trip unless 回程 was sent."""
    if not trip.round_trip:
        return None
    return section or Leg.OUTBOUND


def _filled(value: str | None) -> bool:
    return bool(value and value.strip())


def apply_round_trip(trip: Trip, round_trip: bool, *, return_title, return_notes) -> None:
    """Switch the trip to round trip or one-way, moving its entries' sections.

    `return_title` and `return_notes` are the values the trip will have after
    the same request, so a body that clears them and switches to one-way in
    one go is allowed. Refuses (RoundTripRefused) to go one-way while anything
    is in 回程; checks before it writes.
    """
    if round_trip == trip.round_trip:
        return
    if round_trip:
        for leg in trip.legs:
            if leg.section is None:
                leg.section = Leg.OUTBOUND
    else:
        in_return = sum(1 for leg in trip.legs if leg.section == Leg.RETURN)
        blocking = []
        if in_return:
            blocking.append(
                f"{in_return} {'entry is' if in_return == 1 else 'entries are'} in the return"
            )
        if _filled(return_title) or _filled(return_notes):
            blocking.append("the return has a title or remark")
        if blocking:
            raise RoundTripRefused(
                f"Cannot make the trip one-way: {'; '.join(blocking)}. "
                "Move or delete them first."
            )
        for leg in trip.legs:
            leg.section = None
    trip.round_trip = round_trip


# --- copying --------------------------------------------------------------------


def needs_start_date(source: Trip) -> bool:
    """A copy moves the entries by whole days, which only means something
    when some entry has a departure to move from."""
    return earliest_departure(source) is not None


def copy_legs(db: Session, source: Trip, target: Trip, start_date: date | None) -> list[dict]:
    """Copy `source`'s legs onto `target`: definition carries, state resets.

    Every timed leg moves by the whole days between `start_date` and the
    Taipei calendar day of the source's earliest departure, so clock times
    and the gaps between legs survive. Taiwan keeps no daylight saving, so a
    whole-day shift never moves a clock time. With no departure anywhere
    there is nothing to anchor a shift, and the times are copied unmoved.

    Carried: the journey, its type, direction, ride type, label switches and
    section. Reset: booking state, the booking code and the seat, which
    belong to one booking. The packing-list link cannot carry - a list is
    linked from at most one leg - so it resets too, and the legs that had one
    are returned for the caller to report.
    """
    if not source.legs:
        return []
    first = earliest_departure(source)
    shift = timedelta(0)
    if first is not None and start_date is not None:
        shift = timedelta(days=(start_date - first.astimezone(TAIPEI).date()).days)

    def moved(value: datetime | None) -> datetime | None:
        return None if value is None else value + shift

    unlinked = []
    for leg in source.legs:
        db.add(
            TripLeg(
                trip_id=target.id,
                # Carried: the journey and how it is shown.
                from_place=leg.from_place,
                to_place=leg.to_place,
                departs_at=moved(leg.departs_at),
                arrives_at=moved(leg.arrives_at),
                transport_type=leg.transport_type,
                direction=leg.direction,
                ride_type=leg.ride_type,
                section=leg.section,
                has_booked=leg.has_booked,
                has_paid=leg.has_paid,
                has_collected=leg.has_collected,
                has_booking_code=leg.has_booking_code,
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
