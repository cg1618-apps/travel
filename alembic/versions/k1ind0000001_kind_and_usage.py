"""lists and trips get a kind and a usage status, replacing their flags

`kind` is template / saved / free; `usage` is set exactly when a row is free;
`auto_saved_at` exactly when usage is past, and orders the 自動保存 queue.
Lists gain the `notes` and `archive_note` trips already have. The booleans go:
a list's `saved` and `template`, a trip's `archived` and `template`.

Downgrade restores the booleans from `kind` and drops the rest - usage
statuses and list remarks are lost.

Revision ID: k1ind0000001
Revises: t3rip0000003
Create Date: 2026-10-01

"""

import sqlalchemy as sa

from alembic import op

revision = "k1ind0000001"
down_revision = "t3rip0000003"
branch_labels = None
depends_on = None

KINDS = "'template', 'saved', 'free'"
USAGES = "'in_use', 'upcoming', 'unused', 'past'"

# The flag that meant 保存 on each table before this revision.
SAVED_FLAG = {"packing_list": "saved", "trip": "archived"}


def _add_kind(table: str) -> None:
    op.add_column(table, sa.Column("kind", sa.String(), server_default="free", nullable=False))
    op.add_column(table, sa.Column("usage", sa.String(), nullable=True))
    op.add_column(table, sa.Column("auto_saved_at", sa.DateTime(timezone=True), nullable=True))
    saved = SAVED_FLAG[table]
    # A row that was both a template and saved/archived becomes a template:
    # templates are never dropped, so nothing is lost.
    op.execute(
        f"UPDATE {table} SET kind = CASE WHEN template THEN 'template' "
        f"WHEN {saved} THEN 'saved' ELSE 'free' END"
    )
    op.execute(f"UPDATE {table} SET usage = 'unused' WHERE kind = 'free'")
    op.drop_column(table, "template")
    op.drop_column(table, saved)
    op.create_check_constraint(f"ck_{table}_kind", table, f"kind IN ({KINDS})")
    op.create_check_constraint(f"ck_{table}_usage", table, f"usage IS NULL OR usage IN ({USAGES})")
    op.create_check_constraint(
        f"ck_{table}_usage_iff_free", table, "(kind = 'free') = (usage IS NOT NULL)"
    )
    op.create_check_constraint(
        f"ck_{table}_auto_saved_at_iff_past",
        table,
        "COALESCE(usage = 'past', false) = (auto_saved_at IS NOT NULL)",
    )


def _drop_kind(table: str) -> None:
    saved = SAVED_FLAG[table]
    for name in ("auto_saved_at_iff_past", "usage_iff_free", "usage", "kind"):
        op.drop_constraint(f"ck_{table}_{name}", table, type_="check")
    op.add_column(table, sa.Column(saved, sa.Boolean(), server_default="false", nullable=False))
    op.add_column(table, sa.Column("template", sa.Boolean(), server_default="false", nullable=False))
    op.execute(f"UPDATE {table} SET template = (kind = 'template'), {saved} = (kind = 'saved')")
    op.drop_column(table, "auto_saved_at")
    op.drop_column(table, "usage")
    op.drop_column(table, "kind")


def upgrade() -> None:
    _add_kind("packing_list")
    _add_kind("trip")
    op.add_column("packing_list", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("packing_list", sa.Column("archive_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("packing_list", "archive_note")
    op.drop_column("packing_list", "notes")
    _drop_kind("trip")
    _drop_kind("packing_list")
