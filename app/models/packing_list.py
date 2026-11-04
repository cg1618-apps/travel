"""A packing list. `kind` and `usage` decide which shelf it is on."""

from datetime import date

from sqlalchemy import CheckConstraint, Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import TAIPEI, Leg, Visibility
from app.database import Base
from app.models.base import KindMixin, TimestampMixin, in_clause, kind_constraints


class PackingList(Base, TimestampMixin, KindMixin):
    __tablename__ = "packing_list"
    __table_args__ = (
        CheckConstraint(in_clause("leg", Leg, nullable=True), name="ck_packing_list_leg"),
        CheckConstraint(
            in_clause("visibility", Visibility), name="ck_packing_list_visibility"
        ),
        *kind_constraints("packing_list"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)

    # Nullable, and the reason the timing view works without a trip existing.
    # Ignored while a dated trip leg links this list - see `effective_departure_at`.
    departure_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    #: 備註, the planning remark, and 保存備註, the one written afterwards.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    archive_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    leg: Mapped[str | None] = mapped_column(String, nullable=True)

    # Shared by the two lists of a round trip, rather than each pointing at the
    # other. A self-pointer holds two copies of one fact and can desync - A
    # points at B while B points at C, and nothing complains - and 自動保存
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

    def _leg_departs_at(self):
        return self.trip_leg.departs_at if self.trip_leg is not None else None

    @property
    def effective_departure_at(self) -> date | None:
        """The linked leg's Taipei calendar day when it has a departure time,
        else the list's own date - including while linked to an undated leg."""
        departs = self._leg_departs_at()
        if departs is not None:
            return departs.astimezone(TAIPEI).date()
        return self.departure_at

    @property
    def departure_source(self) -> str:
        """`trip_leg` only while the leg actually supplies the date."""
        return "trip_leg" if self._leg_departs_at() is not None else "list"
