"""筆記, going in and coming out."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.base import NonNullableUpdate, blank_is_null, stripped_links


def _required_title(value: str | None) -> str | None:
    """Stripped; a blank title is refused, not stored."""
    if value is None:
        return None
    title = value.strip()
    if not title:
        raise ValueError("a note needs a title")
    return title


class NoteCreate(BaseModel):
    #: The note's group; stripped, and blank is no group.
    group_name: str | None = None
    title: str = Field(min_length=1)
    description: str | None = None
    links: list[str] = []

    _group = field_validator("group_name")(blank_is_null)
    _title = field_validator("title")(_required_title)
    _links = field_validator("links")(stripped_links)


class NoteUpdate(NonNullableUpdate):
    """All optional. `links`, when present, replaces the whole list, and its
    order is the links' order - which is how links are reordered."""

    non_nullable = ("title", "links")

    group_name: str | None = None
    title: str | None = None
    description: str | None = None
    links: list[str] | None = None

    _group = field_validator("group_name")(blank_is_null)
    _title = field_validator("title")(_required_title)
    _links = field_validator("links")(stripped_links)


class NoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    group_name: str | None
    title: str
    description: str | None
    #: The URLs in order: the link rows, flattened to their `url`.
    links: list[str] = []
    position: int

    @field_validator("links", mode="before")
    @classmethod
    def _link_urls(cls, value):
        return [getattr(link, "url", link) for link in value]


class NoteOrder(BaseModel):
    """Every note, each once, in the order the notes page should read."""

    note_ids: list[int]
