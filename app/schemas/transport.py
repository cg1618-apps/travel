"""Transport going in and coming out."""

from datetime import time as clock_time

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


NOTE_NEEDS_TITLE_OR_LINK = "A note needs a title or at least one link."


def _blank_title_is_null(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def _stripped_links(value: list[str] | None) -> list[str] | None:
    """Each link stripped; a blank one refused rather than silently dropped,
    so a caller that sent an empty row learns it did."""
    if value is None:
        return None
    links = [link.strip() for link in value]
    if any(link == "" for link in links):
        raise ValueError("a link cannot be blank")
    return links


class TransportNoteCreate(BaseModel):
    """A note under a route's 備註. A description alone is not a note: it
    needs a title or at least one link."""

    title: str | None = None
    description: str | None = None
    links: list[str] = []

    _title = field_validator("title")(_blank_title_is_null)
    _links = field_validator("links")(_stripped_links)

    @model_validator(mode="after")
    def _title_or_link(self):
        if self.title is None and not self.links:
            raise ValueError(NOTE_NEEDS_TITLE_OR_LINK)
        return self


class TransportNoteUpdate(NonNullableUpdate):
    """All optional; `links`, when present, replaces the whole list. Whether
    the result still has a title or a link is checked by the router against
    the stored note, because one field alone cannot answer it."""

    non_nullable = ("links",)

    title: str | None = None
    description: str | None = None
    links: list[str] | None = None

    _title = field_validator("title")(_blank_title_is_null)
    _links = field_validator("links")(_stripped_links)


class TransportNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    route_id: int
    title: str | None
    description: str | None
    #: The URLs in order: the link rows, flattened to their `url`.
    links: list[str] = []
    position: int

    @field_validator("links", mode="before")
    @classmethod
    def _link_urls(cls, value):
        return [getattr(link, "url", link) for link in value]


class TransportRouteResponse(TransportRouteBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    position: int
    options: list[TransportOptionResponse] = []
    #: The titled notes shown below `notes` (備註), which is a separate,
    #: plain text column.
    note_entries: list[TransportNoteResponse] = []


class TransportRouteOrder(BaseModel):
    """Every route, each once, in the order the transport page should read."""

    route_ids: list[int]


class TransportOptionOrder(BaseModel):
    """Every option of one route, each once, in the order it should read."""

    option_ids: list[int]
