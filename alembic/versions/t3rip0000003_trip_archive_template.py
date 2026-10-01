"""a trip can be archived, with a remark, and can be a template

`archived` hides a past trip from 其他行程 and from the current-trip rule;
`archive_note` is the after-the-fact remark, separate from the planning
`notes`; `template` offers the trip as a starting point for a new one. The two
flags are independent, like `saved` and `template` on a packing list.

Revision ID: t3rip0000003
Revises: t2rip0000002
Create Date: 2026-10-01

"""

import sqlalchemy as sa

from alembic import op

revision = "t3rip0000003"
down_revision = "t2rip0000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trip", sa.Column("archived", sa.Boolean(), server_default="false", nullable=False)
    )
    op.add_column("trip", sa.Column("archive_note", sa.Text(), nullable=True))
    op.add_column(
        "trip", sa.Column("template", sa.Boolean(), server_default="false", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("trip", "template")
    op.drop_column("trip", "archive_note")
    op.drop_column("trip", "archived")
