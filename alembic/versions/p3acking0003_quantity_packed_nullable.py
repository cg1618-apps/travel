"""packing item quantity_packed may be null

已打包數量 starts with no value instead of 0. A 0 was only ever the default -
"nobody has counted" - and the sheet cannot tell that from "counted, none in
the bag", so every stored 0 becomes null. A real count is untouched.

Downgrade fills the nulls with 0 and restores NOT NULL and the default; a count
someone deliberately set to 0 after this revision is indistinguishable from one
that was never set, which is the state the earlier schema could express.

Revision ID: p3acking0003
Revises: k1ind0000001
Create Date: 2026-10-03

"""

import sqlalchemy as sa

from alembic import op

revision = "p3acking0003"
down_revision = "k1ind0000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "packing_item",
        "quantity_packed",
        existing_type=sa.Integer(),
        nullable=True,
        server_default=None,
    )
    op.execute("UPDATE packing_item SET quantity_packed = NULL WHERE quantity_packed = 0")


def downgrade() -> None:
    op.execute("UPDATE packing_item SET quantity_packed = 0 WHERE quantity_packed IS NULL")
    op.alter_column(
        "packing_item",
        "quantity_packed",
        existing_type=sa.Integer(),
        nullable=False,
        server_default="0",
    )
