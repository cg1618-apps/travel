"""notes on a transport route, each with its links

Two tables: `transport_note` (a title, a description, a position on its
route) and `transport_note_link` (one URL per row, in order). A route's
existing `notes` column - its 備註 - is untouched; these are a separate list
shown below it. Links are rows rather than an array or a text column so that
each one has a position and the sheet backup stays one value per cell.

Every constraint is named, for the reason `p1acking0001` gives.

Revision ID: t2ransport02
Revises: t4rip0000004
Create Date: 2026-11-04

"""

import sqlalchemy as sa

from alembic import op

revision = "t2ransport02"
down_revision = "t4rip0000004"
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
        "transport_note",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("route_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["route_id"],
            ["transport_route.id"],
            name="fk_transport_note_transport_route",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transport_note_route_id", "transport_note", ["route_id"], unique=False)

    op.create_table(
        "transport_note_link",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("note_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["note_id"],
            ["transport_note.id"],
            name="fk_transport_note_link_transport_note",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_transport_note_link_note_id", "transport_note_link", ["note_id"], unique=False
    )


def downgrade() -> None:
    # Children first: each table holds the foreign key to the one above it.
    op.drop_index("ix_transport_note_link_note_id", table_name="transport_note_link")
    op.drop_table("transport_note_link")
    op.drop_index("ix_transport_note_route_id", table_name="transport_note")
    op.drop_table("transport_note")
