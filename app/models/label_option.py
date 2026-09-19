"""The remembered values behind the free-text category and bag fields."""

from sqlalchemy import CheckConstraint, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import LabelKind
from app.database import Base
from app.models.base import TimestampMixin, in_clause


class LabelOption(Base, TimestampMixin):
    """A suggestion, not a reference.

    An item stores its category and bag as text. These rows exist so typing one
    twice is unnecessary, and so a typo can be pruned - which is why deleting
    one leaves the items using it untouched. Renaming one DOES rewrite them,
    because the item holds the text itself and a rename that only touched this
    row would leave the screen showing both spellings.
    """

    __tablename__ = "label_option"
    __table_args__ = (
        CheckConstraint(in_clause("kind", LabelKind), name="ck_label_option_kind"),
        UniqueConstraint("kind", "value", name="uq_label_option_kind_value"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False, index=True)
    value: Mapped[str] = mapped_column(String, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
