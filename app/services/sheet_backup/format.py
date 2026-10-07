"""A column's value to a sheet cell and back, decided by the column's type.

Media's `format_for_sheet` and `parse_from_sheet`, narrowed to the six types
these tables use, with two differences that both follow from restore being a
replacement rather than a merge:

- A timestamp keeps its own offset. Media appends `Z` to whatever `isoformat`
  produced, which is only right for a naive UTC value; these columns are
  `timestamptz`, so the value already says where it is.
- A cell that cannot be read is refused, never dropped to null. Media folds a
  bad cell to None so one hand edit cannot stop a Pull; here the sheet is the
  whole truth, and a null that silently replaced a value would be data loss
  with nothing to say so. `CellRefused` names the tab, the row and the column.
"""

import re
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import Boolean, Column, Date, DateTime, Integer, String, Time

_INTEGER = re.compile(r"-?\d+")


class CellRefused(ValueError):
    """A restore tab holds something its column cannot store."""

    def __init__(self, tab: str, row: int, column: str, problem: str):
        super().__init__(f"{tab}, row {row}, column {column}: {problem}")


def to_sheet(value: Any) -> str:
    """One cell's text. Null is the empty cell, a bool is TRUE or FALSE."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (datetime, date, time)):
        # datetime: ISO 8601 with its offset. date: YYYY-MM-DD. time: HH:MM:SS
        # (with a fraction only if one is stored, so nothing is lost).
        return value.isoformat()
    return str(value)


def from_sheet(column: Column, text: str) -> Any:
    """The value `text` stands for in `column`, or ValueError saying why not.

    The empty cell is null; whether null is allowed is the caller's to check,
    because only it knows the row. Strings are taken verbatim, whitespace and
    all: a `RAW` write stored them exactly, so anything stripped here would be
    a change the backup never made.
    """
    if text == "":
        return None
    kind = column.type
    if isinstance(kind, Boolean):
        if text.upper() == "TRUE":
            return True
        if text.upper() == "FALSE":
            return False
        raise ValueError(f"{text!r} is not TRUE or FALSE")
    if isinstance(kind, Integer):
        if not _INTEGER.fullmatch(text):
            raise ValueError(f"{text!r} is not a whole number")
        return int(text)
    if isinstance(kind, DateTime):
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            raise ValueError(f"{text!r} has no UTC offset")
        return parsed
    if isinstance(kind, Date):
        return date.fromisoformat(text)
    if isinstance(kind, Time):
        return time.fromisoformat(text)
    if isinstance(kind, String):
        return text
    raise TypeError(f"no sheet format for {column.table.name}.{column.name} ({kind})")
