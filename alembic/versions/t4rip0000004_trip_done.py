"""a trip can be marked done

`done` is 已完成, the owner's own mark that a trip is finished with. It is
independent of `kind` and `usage`: a trip moved to 過去使用 is not thereby
done, and a done trip keeps whatever shelf it is on. Every existing trip
starts not done.

Revision ID: t4rip0000004
Revises: p3acking0003
Create Date: 2026-11-04

"""

import sqlalchemy as sa

from alembic import op

revision = "t4rip0000004"
down_revision = "p3acking0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trip", sa.Column("done", sa.Boolean(), server_default="false", nullable=False))


def downgrade() -> None:
    op.drop_column("trip", "done")
