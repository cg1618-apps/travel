"""What a list looks like going in and coming out."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.constants import Leg
from app.schemas.packing_item import PackingItemResponse


class PackingListBase(BaseModel):
    name: str = Field(min_length=1)
    departure_at: date | None = None
    saved: bool = False
    template: bool = False
    leg: Leg | None = None
    pair_id: str | None = None


class PackingListCreate(PackingListBase):
    #: Copy the items of an existing list - recent, saved or template alike.
    copy_from_id: int | None = None

    #: Acknowledgement that creating this list may destroy the oldest working
    #: slot. The first attempt is expected to arrive without it and be refused;
    #: that refusal is the only place the caller learns what would go.
    evict_confirmed: bool = False


class PackingListUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    departure_at: date | None = None
    saved: bool | None = None
    template: bool | None = None
    leg: Leg | None = None
    pair_id: str | None = None
    evict_confirmed: bool = False


class PackingListFields(BaseModel):
    """What every read of a list carries, whichever shape it is asked for."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    departure_at: date | None
    saved: bool
    template: bool
    leg: Leg | None
    pair_id: str | None


class PackingListSummary(PackingListFields):
    """A list without its items, for the index.

    The counts are here rather than on the items the caller does not get: the
    index shows "3 / 11 packed" per list, and sending every item so the client
    can count them would be a page-sized payload to render one fraction.
    """

    item_count: int = 0
    settled_count: int = 0


class PackingListResponse(PackingListFields):
    items: list[PackingItemResponse] = []


class PackingListIndex(BaseModel):
    """The three shelves, and a warning about the next eviction.

    `evict_next` carries what a 409 cannot: the refusal's `detail` is a plain
    string, matching every router in the media tracker and what the frontend's
    fetch wrapper reads. The dialog still needs the list's id to offer "save it
    instead", so that arrives here as data rather than being smuggled into an
    error message. The index is already loaded on the screen where a list gets
    created, so this costs no extra request.
    """

    recent: list[PackingListSummary]
    saved: list[PackingListSummary]
    templates: list[PackingListSummary]
    #: The slot that the next working list would destroy - both halves of a
    #: pair - or empty when there is room.
    evict_next: list[PackingListSummary]
