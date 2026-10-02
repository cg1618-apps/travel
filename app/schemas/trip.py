"""Trips and their legs, going in and coming out."""

from datetime import date, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.constants import Kind, Usage
from app.schemas.base import NonNullableUpdate

ARRIVAL_BEFORE_DEPARTURE = "arrives_at must be after departs_at"


class TripLegBase(BaseModel):
    from_place: str = Field(min_length=1)
    to_place: str = Field(min_length=1)
    departs_at: AwareDatetime
    arrives_at: AwareDatetime
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

    @model_validator(mode="after")
    def _arrives_after_departs(self):
        if self.arrives_at <= self.departs_at:
            raise ValueError(ARRIVAL_BEFORE_DEPARTURE)
        return self


class TripLegUpdate(NonNullableUpdate):
    """All optional. The pair of times is checked against the stored leg by the
    router, because one of them alone cannot be compared."""

    non_nullable = (
        "from_place",
        "to_place",
        "departs_at",
        "arrives_at",
        "booked",
        "paid",
        "collected",
    )

    from_place: str | None = Field(default=None, min_length=1)
    to_place: str | None = Field(default=None, min_length=1)
    departs_at: AwareDatetime | None = None
    arrives_at: AwareDatetime | None = None
    service: str | None = None
    service_number: str | None = None
    seat: str | None = None
    price: int | None = Field(default=None, ge=0)
    ticket_type: str | None = None
    booked: bool | None = None
    paid: bool | None = None
    collected: bool | None = None
    booking_code: str | None = None
    notes: str | None = None
    packing_list_id: int | None = None


class TripLegResponse(TripLegBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    trip_id: int
    packing_list_name: str | None = None


class TripBase(BaseModel):
    name: str = Field(min_length=1)
    notes: str | None = None


class TripUpdate(NonNullableUpdate):
    # `evict_confirmed` is a plain bool, so pydantic already refuses null for it.
    non_nullable = ("name", "kind", "usage")

    name: str | None = Field(default=None, min_length=1)
    notes: str | None = None
    archive_note: str | None = None
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
