"""Shared pieces the model modules build on."""

from enum import StrEnum

from sqlalchemy import DateTime, func
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
    it displays them. Nothing here displays them - `created_at` exists to order
    the three-list cap's eviction - so they come from the database clock, which
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
