"""packing lists

The first tables in this application. `0001_baseline` was deliberately empty so
that the from-zero proof existed before the first column did; this is the
revision that proof starts checking.

Three tables and no fourth. There is no trip table: a packing list carries its
own nullable `departure_at`, because the timing view is the reason the app is
opened and requiring a trip first would be bookkeeping demanded before the app
is useful. Module 2 adds `trip` and a nullable `trip_id`, which is a cheap
column to add later — unlike `visibility`, which ships here unused precisely
because retrofitting the *checks* at every read path is the expensive part.

Every constraint is named. An unnamed one gets a generated name that
`downgrade()` cannot drop, which would turn the platform's rollback hook into a
lie at the moment it is first needed.

Enumerated values are text plus a CheckConstraint rather than a PostgreSQL ENUM
type: adding a member to a PG enum inside a reversible revision is
disproportionate ceremony for five small sets, and the application is
exhaustive over all of them anyway.

Revision ID: 0002_packing
Revises: 0001_baseline
Create Date: 2026-09-19

"""

import sqlalchemy as sa

from alembic import op

revision = "0002_packing"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "label_option",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
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
        sa.CheckConstraint("kind IN ('category', 'bag')", name="ck_label_option_kind"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "value", name="uq_label_option_kind_value"),
    )
    op.create_index("ix_label_option_kind", "label_option", ["kind"], unique=False)

    op.create_table(
        "packing_list",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("departure_at", sa.Date(), nullable=True),
        sa.Column("saved", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("template", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("leg", sa.String(), nullable=True),
        sa.Column("pair_id", sa.String(), nullable=True),
        sa.Column("visibility", sa.String(), server_default="private", nullable=False),
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
        sa.CheckConstraint(
            "leg IS NULL OR leg IN ('outbound', 'return')", name="ck_packing_list_leg"
        ),
        sa.CheckConstraint(
            "visibility IN ('private', 'unlisted', 'public')",
            name="ck_packing_list_visibility",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_packing_list_pair_id", "packing_list", ["pair_id"], unique=False)

    op.create_table(
        "packing_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("list_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("bag", sa.String(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("quantity_packed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unit", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="not_packed", nullable=False),
        sa.Column("timing", sa.String(), server_default="whenever", nullable=False),
        sa.Column(
            "needs_double_check", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("double_checked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
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
        sa.CheckConstraint(
            "status IN ('not_packed', 'packed', 'no_need')", name="ck_packing_item_status"
        ),
        sa.CheckConstraint(
            "timing IN ('whenever', 'night_before', 'day_of', 'just_before')",
            name="ck_packing_item_timing",
        ),
        # ON DELETE CASCADE at the database level, not only cascade= on the
        # relationship: eviction deletes through the ORM, but a DELETE run by
        # hand from psql must not leave orphaned items behind either.
        sa.ForeignKeyConstraint(
            ["list_id"],
            ["packing_list.id"],
            name="fk_packing_item_packing_list",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_packing_item_list_id", "packing_item", ["list_id"], unique=False)


def downgrade() -> None:
    # Children first: packing_item holds the foreign key.
    op.drop_index("ix_packing_item_list_id", table_name="packing_item")
    op.drop_table("packing_item")
    op.drop_index("ix_packing_list_pair_id", table_name="packing_list")
    op.drop_table("packing_list")
    op.drop_index("ix_label_option_kind", table_name="label_option")
    op.drop_table("label_option")
