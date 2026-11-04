"""trip entries get a transport type, label switches and optional times; trips
get a ticket status and can be round trips

`trip_leg`: `transport_type` (every existing entry becomes `other`, which keeps
the full form and all three labels), `direction`, `ride_type`, `section`, and
the four `has_*` switches, all true for existing entries. `departs_at` and
`arrives_at` become nullable, and the time CHECK is replaced by one that allows
equal times and ignores a missing one.

`trip`: `ticket_status` (every existing trip `not_bought`), `round_trip`
(false), `outbound_title`, `return_title`, `return_notes`.

The downgrade refuses, rather than inventing a time, when an entry has a null
time or arrives exactly when it departs - neither fits the old columns.

Revision ID: t5rip0000005
Revises: t2ransport02
Create Date: 2026-11-04

"""

import sqlalchemy as sa

from alembic import op

revision = "t5rip0000005"
down_revision = "t2ransport02"
branch_labels = None
depends_on = None

# Written out rather than imported from app.constants: a revision describes
# the schema as it was on the day, and must not move when the enums do.
TRANSPORT_TYPES = (
    "hsr", "train", "metro", "bus", "coach", "car", "bike", "walk", "flight", "ship", "other",
)
RIDE_TYPES = ("hail", "own_car", "car_rental", "own_bike", "youbike", "moovo", "bike_rental")
FLAGS = ("has_booked", "has_paid", "has_collected", "has_booking_code")


def _in(column: str, values: tuple[str, ...], *, nullable: bool = False) -> str:
    quoted = ", ".join(f"'{value}'" for value in values)
    clause = f"{column} IN ({quoted})"
    return f"{column} IS NULL OR {clause}" if nullable else clause


def upgrade() -> None:
    op.add_column(
        "trip_leg",
        sa.Column("transport_type", sa.String(), server_default="other", nullable=False),
    )
    op.add_column("trip_leg", sa.Column("direction", sa.String(), nullable=True))
    op.add_column("trip_leg", sa.Column("ride_type", sa.String(), nullable=True))
    op.add_column("trip_leg", sa.Column("section", sa.String(), nullable=True))
    for flag in FLAGS:
        op.add_column(
            "trip_leg", sa.Column(flag, sa.Boolean(), server_default="true", nullable=False)
        )
    op.create_check_constraint(
        "ck_trip_leg_transport_type", "trip_leg", _in("transport_type", TRANSPORT_TYPES)
    )
    op.create_check_constraint(
        "ck_trip_leg_ride_type", "trip_leg", _in("ride_type", RIDE_TYPES, nullable=True)
    )
    op.create_check_constraint(
        "ck_trip_leg_section", "trip_leg", _in("section", ("outbound", "return"), nullable=True)
    )

    op.drop_constraint("ck_trip_leg_arrives_after_departs", "trip_leg", type_="check")
    op.alter_column("trip_leg", "departs_at", nullable=True)
    op.alter_column("trip_leg", "arrives_at", nullable=True)
    op.create_check_constraint(
        "ck_trip_leg_arrives_not_before_departs",
        "trip_leg",
        "departs_at IS NULL OR arrives_at IS NULL OR arrives_at >= departs_at",
    )

    op.add_column(
        "trip",
        sa.Column("ticket_status", sa.String(), server_default="not_bought", nullable=False),
    )
    op.create_check_constraint(
        "ck_trip_ticket_status",
        "trip",
        _in("ticket_status", ("not_bought", "not_needed", "bought")),
    )
    op.add_column(
        "trip", sa.Column("round_trip", sa.Boolean(), server_default="false", nullable=False)
    )
    op.add_column("trip", sa.Column("outbound_title", sa.String(), nullable=True))
    op.add_column("trip", sa.Column("return_title", sa.String(), nullable=True))
    op.add_column("trip", sa.Column("return_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    untimed = bind.execute(
        sa.text("SELECT count(*) FROM trip_leg WHERE departs_at IS NULL OR arrives_at IS NULL")
    ).scalar()
    instant = bind.execute(
        sa.text("SELECT count(*) FROM trip_leg WHERE arrives_at = departs_at")
    ).scalar()
    if untimed or instant:
        raise RuntimeError(
            f"Cannot downgrade t5rip0000005: {untimed} trip entries lack a departure or "
            f"arrival time and {instant} arrive exactly when they depart, which the older "
            "schema cannot hold. Give them times (arriving after departing) or delete them "
            "first; this downgrade will not invent a time."
        )

    op.drop_column("trip", "return_notes")
    op.drop_column("trip", "return_title")
    op.drop_column("trip", "outbound_title")
    op.drop_column("trip", "round_trip")
    op.drop_constraint("ck_trip_ticket_status", "trip", type_="check")
    op.drop_column("trip", "ticket_status")

    op.drop_constraint("ck_trip_leg_arrives_not_before_departs", "trip_leg", type_="check")
    op.alter_column("trip_leg", "arrives_at", nullable=False)
    op.alter_column("trip_leg", "departs_at", nullable=False)
    op.create_check_constraint(
        "ck_trip_leg_arrives_after_departs", "trip_leg", "arrives_at > departs_at"
    )

    op.drop_constraint("ck_trip_leg_section", "trip_leg", type_="check")
    op.drop_constraint("ck_trip_leg_ride_type", "trip_leg", type_="check")
    op.drop_constraint("ck_trip_leg_transport_type", "trip_leg", type_="check")
    for flag in reversed(FLAGS):
        op.drop_column("trip_leg", flag)
    op.drop_column("trip_leg", "section")
    op.drop_column("trip_leg", "ride_type")
    op.drop_column("trip_leg", "direction")
    op.drop_column("trip_leg", "transport_type")
