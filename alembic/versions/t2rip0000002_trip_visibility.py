"""a trip carries visibility, like a packing list

A single trip's information is the thing expected to be shared, and a shareable
entity carries `private` / `unlisted` / `public` from the start, everything
`private`. Nothing reads it yet - the same as `packing_list.visibility` - because
the cheap part is the column and the expensive part, later, is the checks.

The values are written out rather than built from `app.constants.Visibility`:
a revision is a record of what the schema was, and must not change when the
enum does. The model builds the same constraint from the enum.

Revision ID: t2rip0000002
Revises: t1rip0000001
Create Date: 2026-10-01

"""

import sqlalchemy as sa

from alembic import op

revision = "t2rip0000002"
down_revision = "t1rip0000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trip",
        sa.Column("visibility", sa.String(), server_default="private", nullable=False),
    )
    op.create_check_constraint(
        "ck_trip_visibility", "trip", "visibility IN ('private', 'unlisted', 'public')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_trip_visibility", "trip", type_="check")
    op.drop_column("trip", "visibility")
