"""transport routes, options and departures

Three tables: a route (from, to), the options on it (a bus line, a train
service) and the departures of each option. The sheet keeps times in four
day-part columns (早 / 中 / 下午 / 晚) that someone has to keep in step with
each other; here a time is a row and the day parts are computed from it, so
they cannot drift.

Every constraint is named, for the reason `p1acking0001` gives.

Revision ID: t1ransport01
Revises: p2acking0002
Create Date: 2026-09-30

"""

import sqlalchemy as sa

from alembic import op

revision = "t1ransport01"
down_revision = "p2acking0002"
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
        "transport_route",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("from_place", sa.String(), nullable=False),
        sa.Column("to_place", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "transport_option",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("route_id", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("advance_ticket", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("route_map_url", sa.String(), nullable=True),
        sa.Column("timetable_url", sa.String(), nullable=True),
        sa.Column("live_url", sa.String(), nullable=True),
        sa.Column("direction", sa.String(), nullable=True),
        sa.Column("line_from", sa.String(), nullable=True),
        sa.Column("line_to", sa.String(), nullable=True),
        sa.Column("board_at", sa.String(), nullable=True),
        sa.Column("alight_at", sa.String(), nullable=True),
        sa.Column("price", sa.Integer(), nullable=True),
        sa.Column("duration", sa.String(), nullable=True),
        sa.Column("headway", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["route_id"],
            ["transport_route.id"],
            name="fk_transport_option_transport_route",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transport_option_route_id", "transport_option", ["route_id"], unique=False)

    op.create_table(
        "transport_departure",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("option_id", sa.Integer(), nullable=False),
        sa.Column("day_type", sa.String(), nullable=False),
        sa.Column("time", sa.Time(), nullable=False),
        sa.Column("irregular", sa.Boolean(), server_default="false", nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "day_type IN ('weekday', 'holiday')", name="ck_transport_departure_day_type"
        ),
        sa.ForeignKeyConstraint(
            ["option_id"],
            ["transport_option.id"],
            name="fk_transport_departure_transport_option",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "option_id", "day_type", "time", name="uq_transport_departure_option_day_time"
        ),
    )
    op.create_index(
        "ix_transport_departure_option_id", "transport_departure", ["option_id"], unique=False
    )


def downgrade() -> None:
    # Children first: each table holds the foreign key to the one above it.
    op.drop_index("ix_transport_departure_option_id", table_name="transport_departure")
    op.drop_table("transport_departure")
    op.drop_index("ix_transport_option_route_id", table_name="transport_option")
    op.drop_table("transport_option")
    op.drop_table("transport_route")
