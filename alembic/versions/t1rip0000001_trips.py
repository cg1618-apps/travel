"""trips, their booked legs, and a list dated by its leg

A trip is a named group of journeys; a leg is one booked journey - the sheet's
This time row. A packing list is linked FROM the leg (`trip_leg.packing_list_id`,
unique) and not the other way round. The earlier `trip_id` intention in
`p1acking0001`'s docstring is superseded: a leg is the thing with a departure,
so the link lives where the date lives, and a trip-level link could not say
which of a pair's two lists belongs to which journey.

Deleting a list clears the link (SET NULL) rather than the booking. The
`ticket_type` label kind is added to `ck_label_option_kind`.

Revision ID: t1rip0000001
Revises: t1ransport01
Create Date: 2026-09-30

"""

import sqlalchemy as sa

from alembic import op

revision = "t1rip0000001"
down_revision = "t1ransport01"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "trip",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "trip_leg",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trip_id", sa.Integer(), nullable=False),
        sa.Column("from_place", sa.String(), nullable=False),
        sa.Column("to_place", sa.String(), nullable=False),
        sa.Column("departs_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("arrives_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("service", sa.String(), nullable=True),
        sa.Column("service_number", sa.String(), nullable=True),
        sa.Column("seat", sa.String(), nullable=True),
        sa.Column("price", sa.Integer(), nullable=True),
        sa.Column("ticket_type", sa.String(), nullable=True),
        sa.Column("booked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("paid", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("collected", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("booking_code", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("packing_list_id", sa.Integer(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("arrives_at > departs_at", name="ck_trip_leg_arrives_after_departs"),
        sa.ForeignKeyConstraint(
            ["trip_id"], ["trip.id"], name="fk_trip_leg_trip", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["packing_list_id"],
            ["packing_list.id"],
            name="fk_trip_leg_packing_list",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("packing_list_id", name="uq_trip_leg_packing_list_id"),
    )
    op.create_index("ix_trip_leg_trip_id", "trip_leg", ["trip_id"], unique=False)

    op.drop_constraint("ck_label_option_kind", "label_option", type_="check")
    op.create_check_constraint(
        "ck_label_option_kind",
        "label_option",
        "kind IN ('category', 'bag', 'location', 'ticket_type')",
    )


def downgrade() -> None:
    # The narrower constraint would refuse these rows, so they go first.
    op.execute("DELETE FROM label_option WHERE kind = 'ticket_type'")
    op.drop_constraint("ck_label_option_kind", "label_option", type_="check")
    op.create_check_constraint(
        "ck_label_option_kind", "label_option", "kind IN ('category', 'bag', 'location')"
    )

    # Children first: trip_leg holds the foreign key to trip.
    op.drop_index("ix_trip_leg_trip_id", table_name="trip_leg")
    op.drop_table("trip_leg")
    op.drop_table("trip")
