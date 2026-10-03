"""What a list looks like going in and coming out."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.constants import Kind, Leg, Usage
from app.schemas.base import NonNullableUpdate
from app.schemas.packing_item import PackingItemResponse


class PackingListBase(BaseModel):
    name: str = Field(min_length=1)
    departure_at: date | None = None
    leg: Leg | None = None
    pair_id: str | None = None
    notes: str | None = None
    archive_note: str | None = None


class PackingListCreate(PackingListBase):
    #: 一般 by default; `template` makes a 範本 - blank, or 當作範本 with
    #: `copy_from_id`. Nothing is created saved: saving is a move. No create
    #: can be refused by the 自動保存 queue, since a new list is never past.
    kind: Literal["free", "template"] = "free"

    #: Copy the items of an existing list, of any kind.
    copy_from_id: int | None = None


class PackingListUpdate(NonNullableUpdate):
    # `evict_confirmed` is not a column, and is a plain bool, so it needs no
    # entry: pydantic already refuses null for it.
    non_nullable = ("name", "kind", "usage")

    name: str | None = Field(default=None, min_length=1)
    departure_at: date | None = None
    #: 保存 or 取消保存. A template is made by creating one.
    kind: Literal["saved", "free"] | None = None
    usage: Usage | None = None
    leg: Leg | None = None
    pair_id: str | None = None
    notes: str | None = None
    archive_note: str | None = None
    #: Acknowledges that 過去使用 may drop the oldest 自動保存 slot. The first
    #: attempt is expected to arrive without it and be refused; that refusal
    #: is the only place the caller learns what would go.
    evict_confirmed: bool = False


class PackingListOrder(BaseModel):
    """Every item on the list, each once, in the order it should read."""

    item_ids: list[int]


class PackingListFields(BaseModel):
    """What every read of a list carries, whichever shape it is asked for."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    #: The EFFECTIVE date: a linked leg's Taipei day, else the list's own.
    departure_at: date | None = Field(validation_alias="effective_departure_at")
    departure_source: Literal["list", "trip_leg"] = "list"
    kind: Kind
    usage: Usage | None
    auto_saved_at: datetime | None
    leg: Leg | None
    pair_id: str | None
    notes: str | None
    archive_note: str | None
    #: Every shelf but 自動保存 is ordered by it, and the leg picker shows it.
    created_at: datetime


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
    """The four shelves, and what the next 過去使用 would drop.

    `evict_next` carries what a 409 cannot: the refusal's `detail` is a plain
    string, matching every router in the media tracker and what the frontend's
    fetch wrapper reads. The dialog still needs the list's id to offer "save it
    instead", so that arrives here as data rather than being smuggled into an
    error message. The index is already loaded on the screen where a list's
    usage is changed, so this costs no extra request.
    """

    #: 一般 lists that are not 過去使用, each with its `usage`. Every shelf
    #: but 自動保存 is newest `created_at` first, then highest `id`.
    free: list[PackingListSummary]
    #: 自動保存: 一般 and 過去使用, newest `auto_saved_at` first.
    auto_saved: list[PackingListSummary]
    saved: list[PackingListSummary]
    templates: list[PackingListSummary]
    #: The slot the next 過去使用 would drop - every auto-saved half of a
    #: pair - or empty when there is room.
    evict_next: list[PackingListSummary]
