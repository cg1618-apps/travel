"""筆記: free-standing notes, each a title, a description and links.

The same shape as `TransportNote` and `TransportNoteLink`, without a route,
with a required title, and with a `group_name` that groups them the way a
packing item's `category` does (docs/business-rules.md, "Groups").
"""

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin


class Note(Base, TimestampMixin):
    __tablename__ = "note"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: The notes sharing a value form a group, kept adjacent in `position`;
    #: null is a group of its own.
    group_name: Mapped[str | None] = mapped_column(String, nullable=True)
    #: Required and non-blank - the schema strips it and refuses an empty one.
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    links = relationship(
        "NoteLink",
        back_populates="note",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="NoteLink.position",
    )


class NoteLink(Base, TimestampMixin):
    """One URL on a note, in the order the note lists them."""

    __tablename__ = "note_link"

    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(
        ForeignKey("note.id", ondelete="CASCADE", name="fk_note_link_note"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(String, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    note = relationship("Note", back_populates="links")
