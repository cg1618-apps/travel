"""One line on a packing list."""

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import Need, Status, Timing
from app.database import Base
from app.models.base import TimestampMixin, in_clause


class PackingItem(Base, TimestampMixin):
    __tablename__ = "packing_item"
    __table_args__ = (
        CheckConstraint(in_clause("status", Status), name="ck_packing_item_status"),
        CheckConstraint(in_clause("timing", Timing), name="ck_packing_item_timing"),
        CheckConstraint(in_clause("need", Need, nullable=True), name="ck_packing_item_need"),
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
    # The sheet's column C: a variant (家鑰匙 under 鑰匙) or a description
    # (long c-c beside bed). Items sharing a name are grouped on screen; each
    # is packed on its own.
    detail: Mapped[str | None] = mapped_column(String, nullable=True)

    # Free text, both of them, with a curated set of suggestions behind them in
    # `label_option`. An item may carry a value that is not in that set.
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    bag: Mapped[str | None] = mapped_column(String, nullable=True)
    # Open, suggested by `label_option` like category and bag.
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    need: Mapped[str | None] = mapped_column(String, nullable=True)

    # A target and a count, which is what forces the number to be numeric:
    # "3 of 5 packed" cannot be computed from "2 pairs". The unit carries what
    # the number cannot. Null quantity means the question does not apply;
    # null quantity_packed means nobody has counted yet, which is not the same
    # as having counted none - so it starts null rather than 0.
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quantity_packed: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
    # The list's order, and with it the order of its groups: a group (the
    # items sharing a category) has no row of its own, so it sits where its
    # items sit. Every write keeps a group's items adjacent.
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    packing_list = relationship("PackingList", back_populates="items")
