"""The closed vocabularies this application is exhaustive over.

The media tracker keeps its vocabularies in `app/utils/constants.py` and serves
them to the client, and most of them carry no database constraint because they
are open lists that grow — a completion level, an ending name. These five are
not that. Each is a small closed set the application branches over, so each one
also gets a `CheckConstraint`, following media's *discriminator* precedent
(`ck_movies_media_type`) rather than its open-vocabulary one.

`StrEnum` so a member compares equal to its stored text and a pydantic schema
can use the same class to produce a 422 before the constraint is ever reached.
"""

from enum import StrEnum


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


TIMING_ORDER: tuple[Timing, ...] = tuple(Timing)
