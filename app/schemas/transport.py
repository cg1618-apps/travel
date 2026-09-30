"""Transport going in and coming out."""

from datetime import time as clock_time
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.constants import DayType


class TransportDepartureCreate(BaseModel):
    day_type: DayType
    time: clock_time
    irregular: bool = False


class NonNullableUpdate(BaseModel):
    """A PATCH body that refuses an explicit null for a required column.

    The update schemas type every field as `X | None = None` so that "omitted"
    means "leave alone", which also lets a caller send null. For a nullable
    column that clears it; for a NOT NULL one it would reach the database as a
    500 (or, for a departure's time, a misleading collision). `non_nullable`
    names those columns, and sending one as null is a 422 instead.
    """

    non_nullable: ClassVar[tuple[str, ...]] = ()

    @model_validator(mode="after")
    def _refuse_explicit_null(self):
        for name in self.non_nullable:
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null.")
        return self


class TransportDepartureUpdate(NonNullableUpdate):
    non_nullable = ("day_type", "time", "irregular")

    day_type: DayType | None = None
    time: clock_time | None = None
    irregular: bool | None = None


class TransportDepartureResponse(TransportDepartureCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    option_id: int


class TransportOptionBase(BaseModel):
    mode: str = Field(min_length=1)
    advance_ticket: bool = False
    route_map_url: str | None = None
    timetable_url: str | None = None
    live_url: str | None = None
    direction: str | None = None
    line_from: str | None = None
    line_to: str | None = None
    board_at: str | None = None
    alight_at: str | None = None
    price: int | None = Field(default=None, ge=0)
    duration: str | None = None
    headway: str | None = None
    notes: str | None = None


class TransportOptionUpdate(NonNullableUpdate):
    non_nullable = ("mode", "advance_ticket", "position")

    mode: str | None = Field(default=None, min_length=1)
    advance_ticket: bool | None = None
    route_map_url: str | None = None
    timetable_url: str | None = None
    live_url: str | None = None
    direction: str | None = None
    line_from: str | None = None
    line_to: str | None = None
    board_at: str | None = None
    alight_at: str | None = None
    price: int | None = Field(default=None, ge=0)
    duration: str | None = None
    headway: str | None = None
    notes: str | None = None
    position: int | None = Field(default=None, ge=0)


class TransportOptionResponse(TransportOptionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    route_id: int
    position: int
    departures: list[TransportDepartureResponse] = []


class TransportRouteBase(BaseModel):
    from_place: str = Field(min_length=1)
    to_place: str = Field(min_length=1)
    notes: str | None = None


class TransportRouteUpdate(NonNullableUpdate):
    non_nullable = ("from_place", "to_place", "position")

    from_place: str | None = Field(default=None, min_length=1)
    to_place: str | None = Field(default=None, min_length=1)
    notes: str | None = None
    position: int | None = Field(default=None, ge=0)


class TransportRouteResponse(TransportRouteBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    position: int
    options: list[TransportOptionResponse] = []
