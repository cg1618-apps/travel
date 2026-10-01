"""Shared pieces the model modules build on."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import Kind, Usage


def in_clause(column: str, vocabulary: type[StrEnum], *, nullable: bool = False) -> str:
    """The SQL for a CheckConstraint restricting `column` to `vocabulary`.

    Built from the enum rather than written out, so adding a member cannot
    leave the constraint behind - a drift that shows up as an insert failing
    on a value the application believes is legal.

    `nullable` matters: `col IN (...)` is NULL, not TRUE, for a NULL column,
    and a CheckConstraint passes on NULL - but saying so explicitly documents
    that the column is allowed to be empty rather than leaving a reader to
    work out SQL's three-valued logic.
    """
    values = ", ".join(f"'{member.value}'" for member in vocabulary)
    clause = f"{column} IN ({values})"
    return f"{column} IS NULL OR {clause}" if nullable else clause


class TimestampMixin:
    """`created_at` and `updated_at`, defaulted by the database.

    The media tracker defaults these in Python from a Taipei-now helper because
    it displays them. Nothing here displays them - `created_at` orders the
    packing-list index - so they come from the database clock, which
    is correct for a row written by a migration or by hand as well as by the
    app, and needs no helper.
    """

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


def _default_usage(context) -> str | None:
    """`unused` for a free row, nothing for a template or a saved one.

    A context-sensitive default because `usage` is required exactly when
    `kind` is free, and a constructor that only names `kind=template` should
    not have to remember to pass `usage=None` as well.
    """
    kind = context.get_current_parameters().get("kind")
    return Usage.UNUSED if kind in (None, Kind.FREE) else None


def kind_constraints(table: str) -> tuple[CheckConstraint, ...]:
    """The four checks that make an impossible kind/usage row unstorable."""
    return (
        CheckConstraint(in_clause("kind", Kind), name=f"ck_{table}_kind"),
        CheckConstraint(in_clause("usage", Usage, nullable=True), name=f"ck_{table}_usage"),
        CheckConstraint("(kind = 'free') = (usage IS NOT NULL)", name=f"ck_{table}_usage_iff_free"),
        CheckConstraint(
            "COALESCE(usage = 'past', false) = (auto_saved_at IS NOT NULL)",
            name=f"ck_{table}_auto_saved_at_iff_past",
        ),
    )


class KindMixin:
    """`kind`, `usage` and `auto_saved_at`, identical on lists and trips.

    自動保存 is `kind = free` with `usage = past`, not a kind of its own; the
    checks in `kind_constraints` keep the three columns consistent.
    """

    kind: Mapped[str] = mapped_column(
        String, nullable=False, default=Kind.FREE, server_default=Kind.FREE
    )
    usage: Mapped[str | None] = mapped_column(String, nullable=True, default=_default_usage)
    #: When the row entered 自動保存; the queue's order. Set iff usage is past.
    auto_saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
