"""The closed vocabularies this application is exhaustive over.

The media tracker keeps its vocabularies in `app/utils/constants.py` and serves
them to the client, and most of them carry no database constraint because they
are open lists that grow — a completion level, an ending name. These are
not that. Each is a small closed set the application branches over, so each one
also gets a `CheckConstraint`, following media's *discriminator* precedent
(`ck_movies_media_type`) rather than its open-vocabulary one.

`StrEnum` so a member compares equal to its stored text and a pydantic schema
can use the same class to produce a 422 before the constraint is ever reached.
"""

from enum import StrEnum
from zoneinfo import ZoneInfo

#: Every leg time is entered and shown here, and a linked list's departure
#: date is the calendar day here - not the server's, not UTC's.
TAIPEI = ZoneInfo("Asia/Taipei")


class Status(StrEnum):
    """Where an item has got to.

    `NO_NEED` is why this is not a boolean: without it a list never reads as
    finished, and the items left unticked cannot say whether they are
    forgotten or deliberately left behind — which is the distinction being
    scanned for at the door.
    """

    NOT_PACKED = "not_packed"
    PACKED = "packed"
    NO_NEED = "no_need"


class Timing(StrEnum):
    """When a thing is supposed to be packed.

    Declared in the order the list renders them, which `TIMING_ORDER` below
    depends on.
    """

    WHENEVER = "whenever"
    NIGHT_BEFORE = "night_before"
    DAY_OF = "day_of"
    JUST_BEFORE = "just_before"


class Leg(StrEnum):
    OUTBOUND = "outbound"
    RETURN = "return"


class Need(StrEnum):
    """Why an item is on the list — the sheet's 需求 column.

    `BRING` is already owned and taken from the item's location; `BUY` has to
    be bought, at that location; `NEED` is needed with bring-or-buy not yet
    decided. Nullable on the item: a row the question does not apply to.
    """

    NEED = "need"
    BRING = "bring"
    BUY = "buy"


class Visibility(StrEnum):
    """Reserved. Nothing reads this yet.

    It ships from the first migration because retrofitting the *checks* at
    every read path is the expensive part, not the column. When sharing is
    built, the flip from Cloudflare Access to public moves the gate from the
    edge into this codebase, and these checks have to work — and be tested for
    refusal — before that lands.
    """

    PRIVATE = "private"
    UNLISTED = "unlisted"
    PUBLIC = "public"


class LabelKind(StrEnum):
    CATEGORY = "category"
    BAG = "bag"
    LOCATION = "location"
    TICKET_TYPE = "ticket_type"


class DayType(StrEnum):
    """The sheet's 平日 / 假日 split. Public holidays are not modelled."""

    WEEKDAY = "weekday"
    HOLIDAY = "holiday"


TIMING_ORDER: tuple[Timing, ...] = tuple(Timing)
