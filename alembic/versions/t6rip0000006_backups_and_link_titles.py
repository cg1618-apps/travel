"""a trip entry can have backups, a round trip gets its overall remark back, and
a note's link can have a title

`trip_leg.backup_of_id` makes a row a 備案 of another entry, and a CHECK keeps
a backup out of the sections and off the packing lists.

`trip.outbound_notes` is the new home of 去程's remark, so `trip.notes` can be
the overall one again. Nothing is moved: text already in `notes` on a round trip
now reads as the overall remark, as the owner decided.

`transport_note_link.title` and `note_link.title` are nullable, so every existing
link simply has no title.

The downgrade deletes the backups first. Only dropping the column would turn
each one into an ordinary entry of its trip, which is worse than losing it.
`outbound_notes` and the link titles are lost with their columns.

Revision ID: t6rip0000006
Revises: n1otes000001
Create Date: 2026-11-05

"""

import sqlalchemy as sa

from alembic import op

revision = "t6rip0000006"
down_revision = "n1otes000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trip", sa.Column("outbound_notes", sa.Text(), nullable=True))

    op.add_column("trip_leg", sa.Column("backup_of_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_trip_leg_backup_of", "trip_leg", "trip_leg", ["backup_of_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_trip_leg_backup_of_id", "trip_leg", ["backup_of_id"])
    op.create_check_constraint(
        "ck_trip_leg_backup_has_no_section_or_list",
        "trip_leg",
        "backup_of_id IS NULL OR (section IS NULL AND packing_list_id IS NULL)",
    )

    op.add_column("transport_note_link", sa.Column("title", sa.String(), nullable=True))
    op.add_column("note_link", sa.Column("title", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("note_link", "title")
    op.drop_column("transport_note_link", "title")

    op.execute("DELETE FROM trip_leg WHERE backup_of_id IS NOT NULL")
    op.drop_constraint("ck_trip_leg_backup_has_no_section_or_list", "trip_leg", type_="check")
    op.drop_index("ix_trip_leg_backup_of_id", table_name="trip_leg")
    op.drop_constraint("fk_trip_leg_backup_of", "trip_leg", type_="foreignkey")
    op.drop_column("trip_leg", "backup_of_id")

    op.drop_column("trip", "outbound_notes")
