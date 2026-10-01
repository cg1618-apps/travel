"""A packing list. One entity; two flags decide what kind of list it is."""

from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import TAIPEI, Leg, Visibility
from app.database import Base
from app.models.base import TimestampMixin, in_clause


class PackingList(Base, TimestampMixin):
    __tablename__ = "packing_list"
    __table_args__ = (
        CheckConstraint(in_clause("leg", Leg, nullable=True), name="ck_packing_list_leg"),
        CheckConstraint(
            in_clause("visibility", Visibility), name="ck_packing_list_visibility"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)

    # Nullable, and the reason the timing view works without a trip existing.
    # Ignored while a trip leg links this list - see `effective_departure_at`.
    departure_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    # `saved` exempts the list from the three-slot cap; `template` offers it as
    # a starting point. Independent: a list can be both, either or neither.
    saved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    template: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    leg: Mapped[str | None] = mapped_column(String, nullable=True)

    # Shared by the two lists of a round trip, rather than each pointing at the
    # other. A self-pointer holds two copies of one fact and can desync - A
    # points at B while B points at C, and nothing complains - and the cap
    # counts a pair as one slot, which is a distinct-count against a shared key
    # and an awkward self-join against a pointer.
    #
    # Navigational only. No logic crosses the pair: nothing infers that what
    # went out must come back, because the return genuinely differs.
    pair_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    visibility: Mapped[str] = mapped_column(
        String, nullable=False, default=Visibility.PRIVATE, server_default=Visibility.PRIVATE
    )

    items = relationship(
        "PackingItem",
        back_populates="packing_list",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PackingItem.position",
    )

    trip_leg = relationship(
        "TripLeg", back_populates="packing_list", uselist=False, passive_deletes=True
    )

    @property
    def effective_departure_at(self) -> date | None:
        """The leg's Taipei calendar day when linked, else the list's own date."""
        if self.trip_leg is not None:
            return self.trip_leg.departs_at.astimezone(TAIPEI).date()
        return self.departure_at

    @property
    def departure_source(self) -> str:
        return "trip_leg" if self.trip_leg is not None else "list"
