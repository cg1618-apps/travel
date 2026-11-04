"""a transport route can belong to a group

`group_name` groups routes the way a packing item's `category` groups items:
the routes sharing a value stay adjacent in `position`, null being a group of
its own. Every existing route is ungrouped, so the existing order is already
one whole group.

Revision ID: t3ransport03
Revises: t5rip0000005
Create Date: 2026-11-04

"""

import sqlalchemy as sa

from alembic import op

revision = "t3ransport03"
down_revision = "t5rip0000005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transport_route", sa.Column("group_name", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("transport_route", "group_name")
