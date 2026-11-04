"""What each trip entry type shows, and which booking labels it carries.

One table, written twice: here, for the server's validation and the readable
sheet tab, and as `LEG_TYPES` in `frontend/src/lib/legTypes.js`, for the form.
The two are kept equal by hand and by `tests/unit/test_leg_types.py`, which
spells this table out in full so that changing it is a visible decision.

A **label** is one of the three booking ticks (`booked`, `paid`, `collected`);
the booking code is a field with the same on/off switch but it is not a label
and never counts towards readiness. Each of the four has a capability:

- `fixed`        - always on; the entry has no switch, and `has_x` is always true;
- `optional_on`  - a per-entry switch, on by default;
- `optional_off` - a per-entry switch, off by default;
- `absent`       - never shown; `has_x` is always false.

Nothing here raises `HTTPException`: `flag_refusals` and `ride_type_refusal`
return the 422 sentences and the router decides.
"""

from dataclasses import dataclass

from app.constants import RideType, TransportType

FIXED = "fixed"
OPTIONAL_ON = "optional_on"
OPTIONAL_OFF = "optional_off"
ABSENT = "absent"

#: The three booking labels, in the order they are ticked.
LABELS = ("booked", "paid", "collected")
#: The four switches, one per label plus the booking code: `has_<name>`.
FLAGS = ("has_booked", "has_paid", "has_collected", "has_booking_code")


@dataclass(frozen=True)
class LegType:
    #: The entry fields the form shows besides from/to, the times, 備註 and the
    #: packing list - API field names, in the form's order.
    fields: tuple[str, ...]
    #: Capability per flag, keyed by the `has_*` column name.
    flags: dict[str, str]
    #: The `ride_type` values this type accepts; empty when it has none.
    ride_types: tuple[RideType, ...] = ()


_TICKET_FIELDS = ("service", "service_number", "seat", "price", "ticket_type")


def _flags(booked: str, paid: str, collected: str, code: str) -> dict[str, str]:
    return dict(zip(FLAGS, (booked, paid, collected, code), strict=True))


_ALL_FIXED = _flags(FIXED, FIXED, FIXED, FIXED)
_ALL_ON = _flags(OPTIONAL_ON, OPTIONAL_ON, OPTIONAL_ON, OPTIONAL_ON)
_NONE = _flags(ABSENT, ABSENT, ABSENT, ABSENT)
_ORDER_ONLY = _flags(OPTIONAL_OFF, OPTIONAL_OFF, ABSENT, OPTIONAL_OFF)

LEG_TYPES: dict[TransportType, LegType] = {
    TransportType.HSR: LegType((*_TICKET_FIELDS, "direction"), _ALL_FIXED),
    TransportType.TRAIN: LegType((*_TICKET_FIELDS, "direction"), _ALL_ON),
    TransportType.COACH: LegType((*_TICKET_FIELDS, "direction"), _ALL_ON),
    TransportType.METRO: LegType(("service", "price", "direction"), _NONE),
    TransportType.BUS: LegType(("service", "service_number", "price", "direction"), _NONE),
    TransportType.CAR: LegType(
        ("ride_type", "service", "service_number", "seat", "price"),
        _ORDER_ONLY,
        (RideType.HAIL, RideType.OWN_CAR, RideType.CAR_RENTAL),
    ),
    TransportType.BIKE: LegType(
        ("ride_type",),
        _ORDER_ONLY,
        (RideType.OWN_BIKE, RideType.YOUBIKE, RideType.MOOVO, RideType.BIKE_RENTAL),
    ),
    TransportType.WALK: LegType((), _NONE),
    # 飛機 and 船 share 其他's form for now - see docs/open-items.md.
    TransportType.FLIGHT: LegType(_TICKET_FIELDS, _ALL_ON),
    TransportType.SHIP: LegType(_TICKET_FIELDS, _ALL_ON),
    TransportType.OTHER: LegType(_TICKET_FIELDS, _ALL_ON),
}


def default_flags(transport_type: str) -> dict[str, bool]:
    """Every `has_*` as a new entry of this type takes it: fixed and
    optional_on are on, optional_off and absent are off."""
    flags = LEG_TYPES[TransportType(transport_type)].flags
    return {flag: flags[flag] in (FIXED, OPTIONAL_ON) for flag in FLAGS}


def flag_refusals(transport_type: str, sent: dict[str, bool]) -> list[str]:
    """Why each sent `has_*` cannot be stored on this type, or nothing.

    `true` for an absent flag, or `false` for a fixed one, would describe a
    switch the form does not have.
    """
    flags = LEG_TYPES[TransportType(transport_type)].flags
    refusals = []
    for flag, value in sent.items():
        if value and flags[flag] == ABSENT:
            refusals.append(f"A {transport_type} entry has no {flag.removeprefix('has_')}.")
        elif not value and flags[flag] == FIXED:
            refusals.append(
                f"A {transport_type} entry always has {flag.removeprefix('has_')}; "
                f"{flag} cannot be false."
            )
    return refusals


def ride_type_refusal(transport_type: str, ride_type: str | None) -> str | None:
    """Why `ride_type` does not belong to this type, or None when it does."""
    if ride_type is None:
        return None
    allowed = LEG_TYPES[TransportType(transport_type)].ride_types
    if ride_type in allowed:
        return None
    if not allowed:
        return f"A {transport_type} entry has no ride_type."
    return (
        f"ride_type {ride_type} is not a {transport_type} ride type; "
        f"expected one of {', '.join(allowed)}."
    )


def enabled_labels(leg) -> list[str]:
    """The labels this entry shows a tick for: its type has them and its
    `has_*` switch is on."""
    flags = LEG_TYPES[TransportType(leg.transport_type)].flags
    return [
        label
        for label in LABELS
        if flags[f"has_{label}"] != ABSENT and getattr(leg, f"has_{label}")
    ]


def unticked_labels(leg) -> list[str]:
    """The enabled labels not yet ticked: what keeps this entry from ready."""
    return [label for label in enabled_labels(leg) if not getattr(leg, label)]


def shows(leg, field: str) -> bool:
    """Whether this entry's type shows `field` (an API field name)."""
    return field in LEG_TYPES[TransportType(leg.transport_type)].fields
