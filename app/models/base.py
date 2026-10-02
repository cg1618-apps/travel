"""Shared pieces the model modules build on."""

from enum import StrEnum

from sqlalchemy import DateTime, String, event, func
from sqlalchemy.orm import Mapped, mapped_column


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
    it displays them. `created_at` is read by the API - it orders the index
    shelves and the leg picker - but is shown only as a date, so they come
    from the database clock, which is correct for a row written by a migration
    or by hand as well as by the app, and needs no helper.
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


def kind_constraints(table: str) -> tuple:
    """The four checks that make an impossible kind/usage row unstorable."""
    from sqlalchemy import CheckConstraint

    from app.constants import Kind, Usage

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
    """`kind`, `usage` and `auto_saved_at`, identical on lists and trips."""

    kind: Mapped[str] = mapped_column(String, nullable=False, default="free", server_default="free")
    usage: Mapped[str | None] = mapped_column(String, nullable=True)
    #: When the row entered 自動保存; the queue's order. Set iff usage is past.
    auto_saved_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


@event.listens_for(KindMixin, "init", propagate=True)
def _default_usage(target, args, kwargs):
    """`unused` for a free row, nothing for a template or a saved one.

    Applied at construction rather than as a column default because `usage` is
    required exactly when `kind` is free, so a constructor that only names
    `kind=template` should not have to pass `usage=None` as well. A column
    default would also swallow an explicit `usage=None` on a free row and
    paper over the very state the database check exists to refuse.
    """
    from app.constants import Kind, Usage

    if "usage" not in kwargs and kwargs.get("kind", Kind.FREE) == Kind.FREE:
        kwargs["usage"] = Usage.UNUSED
