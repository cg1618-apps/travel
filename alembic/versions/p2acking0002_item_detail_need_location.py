"""packing item detail, need and location

The three columns the owner's sheet has and the first packing revision did not:
column C (a variant or description under an item's name), 需求, and 取得地點.
`label_option.kind` widens to take `location`, so a place typed once is
suggested afterwards like a category is.

Revision ID: p2acking0002
Revises: p1acking0001
Create Date: 2026-09-30

"""

import sqlalchemy as sa

from alembic import op

revision = "p2acking0002"
down_revision = "p1acking0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("packing_item", sa.Column("detail", sa.String(), nullable=True))
    op.add_column("packing_item", sa.Column("location", sa.String(), nullable=True))
    op.add_column("packing_item", sa.Column("need", sa.String(), nullable=True))
    op.create_check_constraint(
        "ck_packing_item_need",
        "packing_item",
        "need IS NULL OR need IN ('need', 'bring', 'buy')",
    )
    op.drop_constraint("ck_label_option_kind", "label_option", type_="check")
    op.create_check_constraint(
        "ck_label_option_kind", "label_option", "kind IN ('category', 'bag', 'location')"
    )


def downgrade() -> None:
    # The narrower constraint would refuse the rows this revision allowed.
    op.execute("DELETE FROM label_option WHERE kind = 'location'")
    op.drop_constraint("ck_label_option_kind", "label_option", type_="check")
    op.create_check_constraint(
        "ck_label_option_kind", "label_option", "kind IN ('category', 'bag')"
    )
    op.drop_constraint("ck_packing_item_need", "packing_item", type_="check")
    op.drop_column("packing_item", "need")
    op.drop_column("packing_item", "location")
    op.drop_column("packing_item", "detail")
