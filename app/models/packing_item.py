"""One line on a packing list."""

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import Status, Timing
from app.database import Base
from app.models.base import TimestampMixin, in_clause


class PackingItem(Base, TimestampMixin):
    __tablename__ = "packing_item"
    __table_args__ = (
        CheckConstraint(in_clause("status", Status), name="ck_packing_item_status"),
        CheckConstraint(in_clause("timing", Timing), name="ck_packing_item_timing"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(
        ForeignKey(
            "packing_list.id",
            ondelete="CASCADE",
            # Named, like every other constraint here. An unnamed one gets a
            # generated name that a downgrade cannot drop, which turns the
            # platform's rollback hook into a lie the first time it is needed.
            name="fk_packing_item_packing_list",
        ),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String, nullable=False)

    # Free text, both of them, with a curated set of suggestions behind them in
    # `label_option`. An item may carry a value that is not in that set.
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    bag: Mapped[str | None] = mapped_column(String, nullable=True)

    # A target and a count, which is what forces the number to be numeric:
    # "3 of 5 packed" cannot be computed from "2 pairs". The unit carries what
    # the number cannot. Null quantity means the question does not apply.
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quantity_packed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    unit: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[str] = mapped_column(
        String, nullable=False, default=Status.NOT_PACKED, server_default=Status.NOT_PACKED
    )
    timing: Mapped[str] = mapped_column(
        String, nullable=False, default=Timing.WHENEVER, server_default=Timing.WHENEVER
    )

    # Two fields rather than a fourth status value, because the state worth
    # knowing is PACKED AND STILL UNVERIFIED - the passport is in the bag and
    # nobody has looked at the expiry date. One mutually-exclusive field cannot
    # express that, and that is the state that matters.
    needs_double_check: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    double_checked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    packing_list = relationship("PackingList", back_populates="items")
