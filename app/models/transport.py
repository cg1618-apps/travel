"""Getting between two places: a route, the ways of doing it, and when they run."""

from datetime import time as clock_time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import DayType
from app.database import Base
from app.models.base import TimestampMixin, in_clause


class TransportRoute(Base, TimestampMixin):
    __tablename__ = "transport_route"

    id: Mapped[int] = mapped_column(primary_key=True)
    from_place: Mapped[str] = mapped_column(String, nullable=False)
    to_place: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    options = relationship(
        "TransportOption",
        back_populates="route",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TransportOption.position",
    )


class TransportOption(Base, TimestampMixin):
    """One way of doing a route — a bus line, a train service."""

    __tablename__ = "transport_option"

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[int] = mapped_column(
        ForeignKey(
            "transport_route.id", ondelete="CASCADE", name="fk_transport_option_transport_route"
        ),
        nullable=False,
        index=True,
    )
    mode: Mapped[str] = mapped_column(String, nullable=False)
    advance_ticket: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    route_map_url: Mapped[str | None] = mapped_column(String, nullable=True)
    timetable_url: Mapped[str | None] = mapped_column(String, nullable=True)
    live_url: Mapped[str | None] = mapped_column(String, nullable=True)
    direction: Mapped[str | None] = mapped_column(String, nullable=True)
    # The line's own terminals, and where you actually get on and off. The
    # sheet keeps both because a bus from 台中 to 鹿港 is boarded at 彰化.
    line_from: Mapped[str | None] = mapped_column(String, nullable=True)
    line_to: Mapped[str | None] = mapped_column(String, nullable=True)
    board_at: Mapped[str | None] = mapped_column(String, nullable=True)
    alight_at: Mapped[str | None] = mapped_column(String, nullable=True)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Text, because the sheet's values are ranges ("2h-2h30m").
    duration: Mapped[str | None] = mapped_column(String, nullable=True)
    headway: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    route = relationship("TransportRoute", back_populates="options")
    departures = relationship(
        "TransportDeparture",
        back_populates="option",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="[TransportDeparture.day_type, TransportDeparture.time]",
    )


class TransportDeparture(Base, TimestampMixin):
    """One scheduled time. The sheet's 早/中/下午/晚 columns are computed from it."""

    __tablename__ = "transport_departure"
    __table_args__ = (
        CheckConstraint(in_clause("day_type", DayType), name="ck_transport_departure_day_type"),
        UniqueConstraint(
            "option_id", "day_type", "time", name="uq_transport_departure_option_day_time"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    option_id: Mapped[int] = mapped_column(
        ForeignKey(
            "transport_option.id",
            ondelete="CASCADE",
            name="fk_transport_departure_transport_option",
        ),
        nullable=False,
        index=True,
    )
    day_type: Mapped[str] = mapped_column(String, nullable=False)
    # `time` is the column's name, so the type is imported under another one.
    time: Mapped[clock_time] = mapped_column(Time, nullable=False)
    # The sheet's '*': "not always will we have that time".
    irregular: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    option = relationship("TransportOption", back_populates="departures")
