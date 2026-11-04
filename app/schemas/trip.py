"""Trips and their legs, going in and coming out."""

from datetime import date, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.constants import Kind, Leg, RideType, TicketStatus, TransportType, Usage
from app.schemas.base import NonNullableUpdate
from app.services.domain.leg_types import FLAGS, default_flags, flag_refusals, ride_type_refusal

ARRIVAL_BEFORE_DEPARTURE = "arrives_at must not be before departs_at"


def fill_arrival(departs: datetime | None, arrives: datetime | None) -> datetime | None:
    """The arrival as stored: the departure when only the departure is known."""
    return departs if arrives is None and departs is not None else arrives


def arrival_refusal(departs: datetime | None, arrives: datetime | None) -> str | None:
    if departs is not None and arrives is not None and arrives < departs:
        return ARRIVAL_BEFORE_DEPARTURE
    return None


class TripLegFields(BaseModel):
    """What a leg holds besides its switches, shared by create and response."""

    from_place: str = Field(min_length=1)
    to_place: str = Field(min_length=1)
    departs_at: AwareDatetime | None = None
    arrives_at: AwareDatetime | None = None
    transport_type: TransportType = TransportType.OTHER
    direction: str | None = None
    ride_type: RideType | None = None
    #: 去程 / 回程. The router stores null on a one-way trip, and 去程 for a
    #: round-trip leg sent without one.
    section: Leg | None = None
    service: str | None = None
    service_number: str | None = None
    seat: str | None = None
    price: int | None = Field(default=None, ge=0)
    ticket_type: str | None = None
    booked: bool = False
    paid: bool = False
    collected: bool = False
    booking_code: str | None = None
    notes: str | None = None
    packing_list_id: int | None = None


class TripLegCreate(TripLegFields):
    """A new leg. A `has_*` left out takes the type's default
    (`leg_types.default_flags`); one the type cannot have is a 422, as is a
    `ride_type` that is not the type's."""

    has_booked: bool | None = None
    has_paid: bool | None = None
    has_collected: bool | None = None
    has_booking_code: bool | None = None

    @model_validator(mode="after")
    def _times_and_type(self):
        self.arrives_at = fill_arrival(self.departs_at, self.arrives_at)
        refusal = arrival_refusal(self.departs_at, self.arrives_at)
        if refusal:
            raise ValueError(refusal)
        sent = {flag: getattr(self, flag) for flag in FLAGS if getattr(self, flag) is not None}
        refusals = flag_refusals(self.transport_type, sent)
        ride = ride_type_refusal(self.transport_type, self.ride_type)
        if ride:
            refusals.append(ride)
        if refusals:
            raise ValueError(" ".join(refusals))
        for flag, value in default_flags(self.transport_type).items():
            if getattr(self, flag) is None:
                setattr(self, flag, value)
        return self


class TripLegUpdate(NonNullableUpdate):
    """All optional. The times, the switches and the ride type are checked by
    the router against the leg as it will be, because one field alone cannot
    be judged."""

    non_nullable = (
        "from_place",
        "to_place",
        "transport_type",
        "booked",
        "paid",
        "collected",
        *FLAGS,
    )

    from_place: str | None = Field(default=None, min_length=1)
    to_place: str | None = Field(default=None, min_length=1)
    departs_at: AwareDatetime | None = None
    arrives_at: AwareDatetime | None = None
    transport_type: TransportType | None = None
    direction: str | None = None
    ride_type: RideType | None = None
    section: Leg | None = None
    service: str | None = None
    service_number: str | None = None
    seat: str | None = None
    price: int | None = Field(default=None, ge=0)
    ticket_type: str | None = None
    booked: bool | None = None
    paid: bool | None = None
    collected: bool | None = None
    booking_code: str | None = None
    has_booked: bool | None = None
    has_paid: bool | None = None
    has_collected: bool | None = None
    has_booking_code: bool | None = None
    notes: str | None = None
    packing_list_id: int | None = None


class TripLegResponse(TripLegFields):
    model_config = ConfigDict(from_attributes=True)
    id: int
    trip_id: int
    has_booked: bool
    has_paid: bool
    has_collected: bool
    has_booking_code: bool
    packing_list_name: str | None = None


class TripBase(BaseModel):
    name: str = Field(min_length=1)
    notes: str | None = None


class TripUpdate(NonNullableUpdate):
    # `evict_confirmed` is a plain bool, so pydantic already refuses null for it.
    non_nullable = ("name", "kind", "usage", "done", "ticket_status", "round_trip")

    name: str | None = Field(default=None, min_length=1)
    #: 備註 on a one-way trip; the 去程 remark on a round trip.
    notes: str | None = None
    archive_note: str | None = None
    #: 已準備完成. `true` is refused unless the trip is ready. Independent of
    #: `kind` and `usage`: setting it moves no shelf.
    done: bool | None = None
    ticket_status: TicketStatus | None = None
    #: 單程 (false) or 來回 (true). One-way is refused while anything is in 回程.
    round_trip: bool | None = None
    outbound_title: str | None = None
    return_title: str | None = None
    return_notes: str | None = None
    #: 保存 or 取消保存. A template is made by creating one.
    kind: Literal["saved", "free"] | None = None
    usage: Usage | None = None
    #: Acknowledges that 過去使用 may drop the oldest 自動保存 trip.
    evict_confirmed: bool = False


class TripResponse(TripBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: Kind
    usage: Usage | None
    auto_saved_at: datetime | None
    archive_note: str | None = None
    done: bool = False
    #: Whether `done` may be set: tickets settled and every shown label ticked.
    ready: bool = False
    ticket_status: TicketStatus = TicketStatus.NOT_BOUGHT
    round_trip: bool = False
    outbound_title: str | None = None
    return_title: str | None = None
    return_notes: str | None = None
    created_at: datetime
    legs: list[TripLegResponse] = []


class TripCreate(TripBase):
    """`kind` is 一般 or 範本 - nothing is created saved. `copy_from_id` copies
    another trip, of any kind; `start_date` is the Taipei day its first leg
    moves to, required when that trip has legs."""

    kind: Literal["free", "template"] = "free"
    copy_from_id: int | None = None
    start_date: date | None = None


class TripIndex(BaseModel):
    """The same four shelves as packing lists, plus what 過去使用 would drop."""

    #: 一般 trips that are not 過去使用. Every shelf but 自動保存 is newest
    #: `created_at` first, then highest `id`.
    free: list[TripResponse]
    #: 自動保存: newest `auto_saved_at` first.
    auto_saved: list[TripResponse]
    saved: list[TripResponse]
    templates: list[TripResponse]
    #: The trip the next 過去使用 would drop, or empty when there is room.
    evict_next: list[TripResponse]


class TripIds(BaseModel):
    ids: list[int]


class UnlinkedLeg(BaseModel):
    """A source leg whose packing list the copy did not carry."""

    from_place: str
    to_place: str
    packing_list_name: str


class TripCreated(TripResponse):
    unlinked_from: list[UnlinkedLeg] = []
