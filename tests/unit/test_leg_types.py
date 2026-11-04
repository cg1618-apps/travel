"""The per-type capability table, spelled out in full.

`LEG_TYPES` is written twice - here in `app/services/domain/leg_types.py`
and in `frontend/src/lib/legTypes.js` - and this is the table both are
checked against. Changing a type's form means changing this file, which is
the point: it is a decision, not a refactor.
"""

import pytest

from app.constants import TransportType
from app.services.domain.leg_types import (
    ABSENT,
    FIXED,
    LEG_TYPES,
    OPTIONAL_OFF,
    OPTIONAL_ON,
    default_flags,
    flag_refusals,
    ride_type_refusal,
)

TICKET = ("service", "service_number", "seat", "price", "ticket_type")

#: type: (fields, (has_booked, has_paid, has_collected, has_booking_code), ride types)
EXPECTED = {
    "hsr": ((*TICKET, "direction"), (FIXED, FIXED, FIXED, FIXED), ()),
    "train": ((*TICKET, "direction"), (OPTIONAL_ON,) * 4, ()),
    "coach": ((*TICKET, "direction"), (OPTIONAL_ON,) * 4, ()),
    "metro": (("service", "price", "direction"), (ABSENT,) * 4, ()),
    "bus": (("service", "service_number", "price", "direction"), (ABSENT,) * 4, ()),
    "car": (
        ("ride_type", "service", "service_number", "seat", "price"),
        (OPTIONAL_OFF, OPTIONAL_OFF, ABSENT, OPTIONAL_OFF),
        ("hail", "own_car", "car_rental"),
    ),
    "bike": (
        ("ride_type",),
        (OPTIONAL_OFF, OPTIONAL_OFF, ABSENT, OPTIONAL_OFF),
        ("own_bike", "youbike", "moovo", "bike_rental"),
    ),
    "walk": ((), (ABSENT,) * 4, ()),
    "flight": (TICKET, (OPTIONAL_ON,) * 4, ()),
    "ship": (TICKET, (OPTIONAL_ON,) * 4, ()),
    "other": (TICKET, (OPTIONAL_ON,) * 4, ()),
}


def test_every_transport_type_has_a_row():
    assert set(LEG_TYPES) == set(TransportType) == set(EXPECTED)


@pytest.mark.parametrize("transport_type", sorted(EXPECTED))
def test_the_table_is_the_specified_one(transport_type):
    fields, flags, rides = EXPECTED[transport_type]
    row = LEG_TYPES[TransportType(transport_type)]
    assert row.fields == fields
    assert tuple(row.flags.values()) == flags
    assert tuple(row.flags) == ("has_booked", "has_paid", "has_collected", "has_booking_code")
    assert tuple(row.ride_types) == rides


def test_defaults_are_on_for_fixed_and_optional_on_only():
    assert default_flags("hsr") == dict.fromkeys(
        ("has_booked", "has_paid", "has_collected", "has_booking_code"), True)
    assert default_flags("car") == {"has_booked": False, "has_paid": False,
                                    "has_collected": False, "has_booking_code": False}
    assert default_flags("walk") == dict.fromkeys(default_flags("walk"), False)


def test_a_switch_the_type_does_not_have_is_refused():
    assert flag_refusals("walk", {"has_booked": True})
    assert flag_refusals("hsr", {"has_paid": False})
    assert flag_refusals("car", {"has_collected": True})
    # Mirrors: the same switches, the way the type allows them.
    assert flag_refusals("walk", {"has_booked": False}) == []
    assert flag_refusals("hsr", {"has_paid": True}) == []
    assert flag_refusals("car", {"has_collected": False, "has_booked": True}) == []


def test_a_ride_type_must_be_the_types_own():
    assert ride_type_refusal("car", "youbike")
    assert ride_type_refusal("train", "hail")
    assert ride_type_refusal("car", "hail") is None
    assert ride_type_refusal("bike", "youbike") is None
    assert ride_type_refusal("train", None) is None
