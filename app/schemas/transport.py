"""Transport going in and coming out."""

from datetime import time as clock_time

from pydantic import BaseModel, ConfigDict, Field

from app.constants import DayType
from app.schemas.base import NonNullableUpdate


class TransportDepartureCreate(BaseModel):
    day_type: DayType
    time: clock_time
    irregular: bool = False


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
