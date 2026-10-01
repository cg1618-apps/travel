"""A trip and its booked legs."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import Visibility
from app.database import Base
from app.models.base import KindMixin, TimestampMixin, in_clause, kind_constraints


class Trip(Base, TimestampMixin, KindMixin):
    __tablename__ = "trip"
    __table_args__ = (
        CheckConstraint(in_clause("visibility", Visibility), name="ck_trip_visibility"),
        *kind_constraints("trip"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # `archive_note` is 保存備註, the remark written afterwards, kept apart
    # from the planning `notes`. Which shelf the trip is on is `kind`/`usage`.
    archive_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # A single trip is the thing expected to be shared. Nothing reads this yet,
    # as with `PackingList.visibility`: the column is carried now so that the
    # checks, when they come, have something to check.
    visibility: Mapped[str] = mapped_column(
        String, nullable=False, default=Visibility.PRIVATE, server_default=Visibility.PRIVATE
    )

    legs = relationship(
        "TripLeg",
        back_populates="trip",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TripLeg.departs_at",
    )


class TripLeg(Base, TimestampMixin):
    """One booked journey — the sheet's This time row."""

    __tablename__ = "trip_leg"
    __table_args__ = (
        CheckConstraint("arrives_at > departs_at", name="ck_trip_leg_arrives_after_departs"),
        # One leg per list: a list is packed for one journey.
        UniqueConstraint("packing_list_id", name="uq_trip_leg_packing_list_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(
        ForeignKey("trip.id", ondelete="CASCADE", name="fk_trip_leg_trip"),
        nullable=False,
        index=True,
    )
    from_place: Mapped[str] = mapped_column(String, nullable=False)
    to_place: Mapped[str] = mapped_column(String, nullable=False)
    departs_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    arrives_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    service: Mapped[str | None] = mapped_column(String, nullable=True)
    # Text: an identifier, not a quantity.
    service_number: Mapped[str | None] = mapped_column(String, nullable=True)
    seat: Mapped[str | None] = mapped_column(String, nullable=True)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ticket_type: Mapped[str | None] = mapped_column(String, nullable=True)
    # Steps in order, recorded separately: paying without having collected the
    # ticket is a real state.
    booked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    collected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    booking_code: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # SET NULL: deleting the packing list must not delete a booking.
    packing_list_id: Mapped[int | None] = mapped_column(
        ForeignKey("packing_list.id", ondelete="SET NULL", name="fk_trip_leg_packing_list"),
        nullable=True,
    )

    trip = relationship("Trip", back_populates="legs")
    packing_list = relationship("PackingList", back_populates="trip_leg")

    @property
    def packing_list_name(self) -> str | None:
        return self.packing_list.name if self.packing_list else None
