"""A trip and its entries (legs)."""

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

from app.constants import Leg, RideType, TicketStatus, TransportType, Visibility
from app.database import Base
from app.models.base import KindMixin, TimestampMixin, in_clause, kind_constraints


class Trip(Base, TimestampMixin, KindMixin):
    __tablename__ = "trip"
    __table_args__ = (
        CheckConstraint(in_clause("visibility", Visibility), name="ck_trip_visibility"),
        CheckConstraint(in_clause("ticket_status", TicketStatus), name="ck_trip_ticket_status"),
        *kind_constraints("trip"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    #: The trip's 備註 when one-way; the 去程 remark on a round trip, so nothing
    #: moves when `round_trip` is toggled.
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

    # 已準備完成: the owner's mark that the trip is ready. Only a ready trip can
    # be marked, and a write that makes it not ready clears it in the same
    # transaction - see `app.services.domain.trip`. Independent of `kind` and
    # `usage` on purpose - see docs/notes/decisions.md.
    done: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    #: 未買票 / 無需買票 / 已買票. Only `not_bought` keeps the trip from ready.
    ticket_status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=TicketStatus.NOT_BOUGHT,
        server_default=TicketStatus.NOT_BOUGHT,
    )

    #: 單程 or 來回. A round trip shows its entries in two sections, 去程 and
    #: 回程, each with a title and a remark (`notes` is the 去程 one).
    round_trip: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    #: Kept, but not shown, when the trip goes back to one-way.
    outbound_title: Mapped[str | None] = mapped_column(String, nullable=True)
    return_title: Mapped[str | None] = mapped_column(String, nullable=True)
    return_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    legs = relationship(
        "TripLeg",
        back_populates="trip",
        cascade="all, delete-orphan",
        passive_deletes=True,
        # Undated entries last, then creation order. A lambda because TripLeg
        # is declared below.
        order_by=lambda: (TripLeg.departs_at.asc().nulls_last(), TripLeg.id),
    )

    @property
    def ready(self) -> bool:
        """Whether `done` may be set. The rule is `domain.trip.is_ready`'s."""
        from app.services.domain.trip import is_ready  # the domain imports the models

        return is_ready(self)


class TripLeg(Base, TimestampMixin):
    """One entry of a trip (一段) — the sheet's This time row. The table and
    the API paths keep the older name, leg."""

    __tablename__ = "trip_leg"
    __table_args__ = (
        # Both times are optional. When both are set, arriving at the moment of
        # departure is allowed: the server fills `arrives_at` from
        # `departs_at` when only the departure is known.
        CheckConstraint(
            "departs_at IS NULL OR arrives_at IS NULL OR arrives_at >= departs_at",
            name="ck_trip_leg_arrives_not_before_departs",
        ),
        CheckConstraint(
            in_clause("transport_type", TransportType), name="ck_trip_leg_transport_type"
        ),
        CheckConstraint(
            in_clause("ride_type", RideType, nullable=True), name="ck_trip_leg_ride_type"
        ),
        CheckConstraint(in_clause("section", Leg, nullable=True), name="ck_trip_leg_section"),
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
    departs_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    arrives_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: 高鐵, 火車, ... What the entry shows is `LEG_TYPES[transport_type]` in
    #: `app.services.domain.leg_types`.
    transport_type: Mapped[str] = mapped_column(
        String, nullable=False, default=TransportType.OTHER, server_default=TransportType.OTHER
    )
    #: 方向, free text.
    direction: Mapped[str | None] = mapped_column(String, nullable=True)
    #: 乘車類型 (car) or 類型 (bike). The CHECK is over the union; which value
    #: belongs to which type is the router's to refuse.
    ride_type: Mapped[str | None] = mapped_column(String, nullable=True)
    #: 去程 or 回程 on a round trip; null on a one-way trip.
    section: Mapped[str | None] = mapped_column(String, nullable=True)
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
    # Whether this entry shows each label, and the code, at all. Constrained by
    # its type: a fixed one is always true, an absent one always false. True by
    # default because `other`, the default type, has every one optional and on.
    has_booked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    has_paid: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    has_collected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    has_booking_code: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
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
