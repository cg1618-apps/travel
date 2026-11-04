"""筆記: notes with links, grouped

Two tables, the shape of `transport_note` and `transport_note_link` without a
route: `note` (a group name, a required title, a description, a position) and
`note_link` (one URL per row, in order).

Every constraint is named, for the reason `p1acking0001` gives.

Revision ID: n1otes000001
Revises: t3ransport03
Create Date: 2026-11-04

"""

import sqlalchemy as sa

from alembic import op

revision = "n1otes000001"
down_revision = "t3ransport03"
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
        "note",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_name", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "note_link",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("note_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["note_id"], ["note.id"], name="fk_note_link_note", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_note_link_note_id", "note_link", ["note_id"], unique=False)


def downgrade() -> None:
    # Child first: it holds the foreign key.
    op.drop_index("ix_note_link_note_id", table_name="note_link")
    op.drop_table("note_link")
    op.drop_table("note")
