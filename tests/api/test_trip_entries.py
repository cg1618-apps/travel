"""Trip entries: transport types and their switches, optional times, readiness
and 已準備完成, and one-way and round trips.

Most of what is here is a refusal, so most fixtures are load-bearing: a done
trip whose readiness a write can break, an entry with an enabled unticked
label, an entry in 回程. Each refusal has its mirror on the same fixture.
"""

from datetime import datetime

import pytest

TPE = "+08:00"
DEPARTS = f"2026-11-20T08:00:00{TPE}"
ARRIVES = f"2026-11-20T09:30:00{TPE}"


def at(value):
    return datetime.fromisoformat(value) if value else None


@pytest.fixture
def trip(client):
    return client.post("/api/trips", json={"name": "台中"}).json()


def add(client, trip, **fields):
    body = {"from_place": "台北", "to_place": "台中", **fields}
    return client.post(f"/api/trips/{trip['id']}/legs", json=body)


def patch_leg(client, leg, **fields):
    return client.patch(f"/api/trip-legs/{leg['id']}", json=fields)


def patch_trip(client, trip, **fields):
    return client.patch(f"/api/trips/{trip['id']}", json=fields)


def flags(leg):
    return tuple(leg[f] for f in ("has_booked", "has_paid", "has_collected", "has_booking_code"))


# --- types and switches -----------------------------------------------------------


def test_an_entry_without_a_type_is_other_with_every_switch_on(client, trip):
    leg = add(client, trip).json()
    assert leg["transport_type"] == "other"
    assert flags(leg) == (True, True, True, True)
    assert (leg["direction"], leg["ride_type"], leg["section"]) == (None, None, None)


@pytest.mark.parametrize(
    "transport_type,expected",
    [
        ("hsr", (True, True, True, True)),
        ("train", (True, True, True, True)),
        ("metro", (False, False, False, False)),
        ("car", (False, False, False, False)),
        ("walk", (False, False, False, False)),
    ],
)
def test_switches_not_sent_take_the_types_defaults(client, trip, transport_type, expected):
    assert flags(add(client, trip, transport_type=transport_type).json()) == expected


def test_a_sent_switch_wins_over_the_default(client, trip):
    leg = add(client, trip, transport_type="train", has_collected=False).json()
    assert flags(leg) == (True, True, False, True)


@pytest.mark.parametrize(
    "fields",
    [
        {"transport_type": "walk", "has_booked": True},  # absent label switched on
        {"transport_type": "hsr", "has_paid": False},  # fixed label switched off
        {"transport_type": "car", "has_collected": True},
        {"transport_type": "hsr", "has_booking_code": False},
    ],
)
def test_a_switch_the_type_cannot_have_is_a_422(client, trip, fields):
    assert add(client, trip, **fields).status_code == 422
    # Mirror: the same type, the switch left to its default.
    type_only = {"transport_type": fields["transport_type"]}
    assert add(client, trip, **type_only).status_code == 201


def test_an_unknown_type_is_a_422(client, trip):
    assert add(client, trip, transport_type="rocket").status_code == 422
    assert add(client, trip, transport_type="ship").status_code == 201


@pytest.mark.parametrize(
    "transport_type,ride_type",
    [("car", "youbike"), ("bike", "hail"), ("train", "hail"), ("walk", "own_bike")],
)
def test_a_ride_type_of_another_type_is_a_422(client, trip, transport_type, ride_type):
    assert add(client, trip, transport_type=transport_type, ride_type=ride_type).status_code == 422


@pytest.mark.parametrize("transport_type,ride_type", [("car", "car_rental"), ("bike", "youbike")])
def test_a_ride_type_of_the_type_is_kept(client, trip, transport_type, ride_type):
    leg = add(client, trip, transport_type=transport_type, ride_type=ride_type).json()
    assert leg["ride_type"] == ride_type


def test_a_patch_changing_the_type_resets_unsent_switches(client, trip):
    leg = add(client, trip, transport_type="train", has_collected=False).json()
    to_hsr = patch_leg(client, leg, transport_type="hsr")
    assert to_hsr.status_code == 200
    assert flags(to_hsr.json()) == (True, True, True, True)
    to_car = patch_leg(client, leg, transport_type="car", has_booked=True).json()
    assert flags(to_car) == (True, False, False, False)


def test_a_patch_judges_switches_against_the_new_type(client, trip):
    leg = add(client, trip, transport_type="train").json()
    assert patch_leg(client, leg, transport_type="walk", has_paid=True).status_code == 422
    assert patch_leg(client, leg, has_paid=False).status_code == 200  # train: optional
    hsr = patch_leg(client, leg, transport_type="hsr").json()
    assert patch_leg(client, hsr, has_paid=False).status_code == 422  # hsr: fixed
    assert flags(client.get(f"/api/trips/{trip['id']}").json()["legs"][0]) == (True,) * 4


def test_a_patch_ride_type_is_judged_against_the_type(client, trip):
    leg = add(client, trip, transport_type="car").json()
    assert patch_leg(client, leg, ride_type="moovo").status_code == 422
    assert patch_leg(client, leg, ride_type="hail").json()["ride_type"] == "hail"


def test_hidden_values_are_kept_across_a_type_change(client, trip):
    leg = add(client, trip, transport_type="car", ride_type="hail", seat="3A",
              direction="北上").json()
    walked = patch_leg(client, leg, transport_type="walk").json()
    assert (walked["ride_type"], walked["seat"], walked["direction"]) == ("hail", "3A", "北上")
    back = patch_leg(client, leg, transport_type="car").json()
    assert back["ride_type"] == "hail"


@pytest.mark.parametrize("field", ["transport_type", "has_booked", "has_booking_code"])
def test_a_null_type_or_switch_is_a_422(client, trip, field):
    leg = add(client, trip).json()
    assert patch_leg(client, leg, **{field: None}).status_code == 422


# --- times ------------------------------------------------------------------------


def test_both_times_are_optional(client, trip):
    leg = add(client, trip).json()
    assert (leg["departs_at"], leg["arrives_at"]) == (None, None)


def test_a_departure_alone_fills_the_arrival(client, trip):
    leg = add(client, trip, departs_at=DEPARTS).json()
    assert at(leg["arrives_at"]) == at(DEPARTS)


def test_an_arrival_alone_is_allowed(client, trip):
    leg = add(client, trip, arrives_at=ARRIVES).json()
    assert (leg["departs_at"], at(leg["arrives_at"])) == (None, at(ARRIVES))


def test_arriving_when_departing_is_allowed_and_before_is_a_422(client, trip):
    assert add(client, trip, departs_at=DEPARTS, arrives_at=DEPARTS).status_code == 201
    bad = add(client, trip, departs_at=ARRIVES, arrives_at=DEPARTS)
    assert bad.status_code == 422
    assert "arrives_at must not be before departs_at" in bad.text


def test_a_patch_setting_the_departure_on_an_untimed_entry_fills_the_arrival(client, trip):
    leg = add(client, trip).json()
    body = patch_leg(client, leg, departs_at=DEPARTS).json()
    assert at(body["arrives_at"]) == at(DEPARTS)


def test_a_patch_moving_the_departure_after_the_arrival_is_a_422(client, trip):
    leg = add(client, trip, departs_at=DEPARTS, arrives_at=ARRIVES).json()
    bad = patch_leg(client, leg, departs_at=f"2026-11-20T10:00:00{TPE}")
    assert bad.status_code == 422
    assert bad.json()["detail"] == "arrives_at must not be before departs_at"
    assert patch_leg(client, leg, departs_at=f"2026-11-20T09:00:00{TPE}").status_code == 200


def test_times_can_be_cleared(client, trip):
    leg = add(client, trip, departs_at=DEPARTS, arrives_at=ARRIVES).json()
    body = patch_leg(client, leg, departs_at=None, arrives_at=None).json()
    assert (body["departs_at"], body["arrives_at"]) == (None, None)


def test_entries_read_by_departure_untimed_last_then_id(client, trip):
    untimed = add(client, trip, to_place="untimed").json()
    later = add(client, trip, to_place="later", departs_at=ARRIVES).json()
    sooner = add(client, trip, to_place="sooner", departs_at=DEPARTS).json()
    untimed_too = add(client, trip, to_place="untimed too").json()
    legs = client.get(f"/api/trips/{trip['id']}").json()["legs"]
    assert [leg["id"] for leg in legs] == [sooner["id"], later["id"], untimed["id"],
                                           untimed_too["id"]]


def test_a_list_linked_to_an_untimed_entry_keeps_its_own_date(client, trip):
    lst = client.post("/api/packing-lists", json={"name": "l", "departure_at": "2026-12-01"}).json()
    leg = add(client, trip, packing_list_id=lst["id"]).json()
    body = client.get(f"/api/packing-lists/{lst['id']}").json()
    assert (body["departure_at"], body["departure_source"]) == ("2026-12-01", "list")
    # Mirror: once the entry has a time, its Taipei day wins.
    patch_leg(client, leg, departs_at=DEPARTS)
    body = client.get(f"/api/packing-lists/{lst['id']}").json()
    assert (body["departure_at"], body["departure_source"]) == ("2026-11-20", "trip_leg")


# --- readiness and 已準備完成 ---------------------------------------------------------


@pytest.fixture
def unready(client, trip):
    """Tickets settled, and one train entry with all three labels enabled and
    only `booked` ticked. Load-bearing: without an enabled unticked label
    there is nothing for readiness to refuse on."""
    patch_trip(client, trip, ticket_status="not_needed")
    leg = add(client, trip, transport_type="train", booked=True).json()
    return leg


def test_a_trip_with_an_unticked_label_cannot_be_marked_done(client, trip, unready):
    refused = patch_trip(client, trip, done=True)
    assert refused.status_code == 422
    assert refused.json()["detail"] == "The trip is not ready: 1 entry has unticked labels."
    body = client.get(f"/api/trips/{trip['id']}").json()
    assert (body["done"], body["ready"]) == (False, False)


def test_ticking_every_label_makes_it_ready(client, trip, unready):
    # The mirror on the same fixture.
    patch_leg(client, unready, paid=True, collected=True)
    assert client.get(f"/api/trips/{trip['id']}").json()["ready"] is True
    assert patch_trip(client, trip, done=True).json()["done"] is True


def test_a_label_switched_off_does_not_count(client, trip, unready):
    patch_leg(client, unready, has_paid=False, has_collected=False)
    assert patch_trip(client, trip, done=True).status_code == 200


def test_the_booking_code_does_not_count(client, trip, unready):
    patch_leg(client, unready, paid=True, collected=True)
    # The code switch is on and the code empty, and the trip is still ready.
    assert client.get(f"/api/trips/{trip['id']}").json()["ready"] is True


def test_tickets_not_bought_keeps_a_trip_from_ready(client, trip):
    refused = patch_trip(client, trip, done=True)
    assert refused.status_code == 422
    assert refused.json()["detail"] == "The trip is not ready: tickets not bought."
    # Mirror: settled in the same body, and marked.
    both = patch_trip(client, trip, ticket_status="bought", done=True)
    assert both.status_code == 200 and both.json()["done"] is True


def test_both_reasons_are_named(client, trip):
    add(client, trip, transport_type="hsr")
    add(client, trip, transport_type="train")
    detail = patch_trip(client, trip, done=True).json()["detail"]
    assert detail == "The trip is not ready: tickets not bought; 2 entries have unticked labels."


def test_a_trip_of_walks_only_needs_its_tickets(client, trip):
    add(client, trip, transport_type="walk")
    add(client, trip, transport_type="metro")
    assert patch_trip(client, trip, ticket_status="not_needed", done=True).status_code == 200


def test_unticking_is_still_allowed(client, trip, unready):
    patch_leg(client, unready, paid=True, collected=True)
    patch_trip(client, trip, done=True)
    assert patch_trip(client, trip, done=False).json()["done"] is False


@pytest.fixture
def done_trip(client, trip, unready):
    patch_leg(client, unready, paid=True, collected=True)
    assert patch_trip(client, trip, done=True).json()["done"] is True
    return unready


def done(client, trip):
    return client.get(f"/api/trips/{trip['id']}").json()["done"]


def test_unticking_a_label_clears_done(client, trip, done_trip):
    assert patch_leg(client, done_trip, paid=False).status_code == 200
    assert done(client, trip) is False


def test_enabling_a_label_clears_done(client, trip, done_trip):
    leg = add(client, trip, transport_type="car", has_booked=False).json()
    assert done(client, trip) is True  # mirror: an entry with nothing enabled
    patch_leg(client, leg, has_booked=True)
    assert done(client, trip) is False


def test_adding_an_unticked_entry_clears_done(client, trip, done_trip):
    add(client, trip, transport_type="hsr")
    assert done(client, trip) is False


def test_adding_a_settled_entry_keeps_done(client, trip, done_trip):
    add(client, trip, transport_type="walk")
    assert done(client, trip) is True


def test_changing_a_type_clears_done_when_it_enables_a_label(client, trip, done_trip):
    leg = add(client, trip, transport_type="walk").json()
    patch_leg(client, leg, transport_type="hsr")
    assert done(client, trip) is False


def test_tickets_back_to_not_bought_clears_done(client, trip, done_trip):
    body = patch_trip(client, trip, ticket_status="not_bought").json()
    assert body["done"] is False


def test_deleting_an_entry_never_sets_done(client, trip, unready):
    client.delete(f"/api/trip-legs/{unready['id']}")
    body = client.get(f"/api/trips/{trip['id']}").json()
    assert (body["ready"], body["done"]) == (True, False)


def test_an_unknown_ticket_status_is_a_422(client, trip):
    assert patch_trip(client, trip, ticket_status="maybe").status_code == 422
    assert patch_trip(client, trip, ticket_status=None).status_code == 422
    assert patch_trip(client, trip, ticket_status="bought").status_code == 200


# --- one-way and round trips --------------------------------------------------------


def test_a_new_trip_is_one_way_with_no_tickets(trip):
    assert (trip["round_trip"], trip["ticket_status"]) == (False, "not_bought")
    assert (trip["outbound_title"], trip["return_title"], trip["return_notes"]) == (None,) * 3


def test_a_one_way_entry_has_no_section(client, trip):
    assert add(client, trip, section="return").json()["section"] is None


def test_going_round_trip_puts_every_entry_in_the_outbound(client, trip):
    legs = [add(client, trip).json(), add(client, trip).json()]
    assert patch_trip(client, trip, round_trip=True).json()["round_trip"] is True
    sections = [leg["section"] for leg in client.get(f"/api/trips/{trip['id']}").json()["legs"]]
    assert sections == ["outbound", "outbound"]
    assert len(legs) == 2


def test_a_round_trip_entry_defaults_to_the_outbound(client, trip):
    patch_trip(client, trip, round_trip=True)
    assert add(client, trip).json()["section"] == "outbound"
    assert add(client, trip, section="return").json()["section"] == "return"


def test_an_entry_moves_between_sections(client, trip):
    patch_trip(client, trip, round_trip=True)
    leg = add(client, trip).json()
    assert patch_leg(client, leg, section="return").json()["section"] == "return"
    assert patch_leg(client, leg, section="outbound").json()["section"] == "outbound"


@pytest.fixture
def round_trip(client, trip):
    patch_trip(client, trip, round_trip=True, outbound_title="去台中", outbound_notes="靠窗", notes="帶傘")
    return trip


def test_one_way_is_refused_while_an_entry_is_in_the_return(client, round_trip):
    leg = add(client, round_trip, section="return").json()
    refused = patch_trip(client, round_trip, round_trip=False)
    assert refused.status_code == 422
    assert "1 entry is in the return" in refused.json()["detail"]
    assert client.get(f"/api/trips/{round_trip['id']}").json()["round_trip"] is True
    # Mirror: moved out of 回程, the switch goes through.
    patch_leg(client, leg, section="outbound")
    assert patch_trip(client, round_trip, round_trip=False).status_code == 200


@pytest.mark.parametrize("field", ["return_title", "return_notes"])
def test_one_way_is_refused_while_the_return_has_a_title_or_remark(client, round_trip, field):
    patch_trip(client, round_trip, **{field: "回彰化"})
    refused = patch_trip(client, round_trip, round_trip=False)
    assert refused.status_code == 422
    assert "title or remark" in refused.json()["detail"]
    # Mirror: cleared in the same body, allowed.
    assert patch_trip(client, round_trip, round_trip=False, **{field: None}).status_code == 200


def test_going_one_way_clears_sections_and_keeps_the_rest(client, round_trip):
    add(client, round_trip)
    body = patch_trip(client, round_trip, round_trip=False).json()
    assert [leg["section"] for leg in body["legs"]] == [None]
    assert (body["notes"], body["outbound_title"], body["outbound_notes"]) == ("帶傘", "去台中", "靠窗")


def test_the_overall_remark_is_apart_from_the_section_remarks(client, trip):
    patch_trip(client, trip, notes="整趟")
    body = patch_trip(client, trip, round_trip=True, outbound_notes="去", return_notes="回").json()
    assert (body["notes"], body["outbound_notes"], body["return_notes"]) == ("整趟", "去", "回")
    assert patch_trip(client, trip, outbound_notes="改").json()["notes"] == "整趟"
    assert patch_trip(client, trip, notes="也改").json()["outbound_notes"] == "改"


def test_the_outbound_remark_does_not_block_one_way_and_comes_back(client, round_trip):
    """Only 回程 refuses: 去程's title and remark are kept, not shown, and come
    back with the round trip."""
    assert patch_trip(client, round_trip, round_trip=False).status_code == 200
    assert patch_trip(client, round_trip, round_trip=True).json()["outbound_notes"] == "靠窗"


def test_a_null_round_trip_is_a_422(client, trip):
    assert patch_trip(client, trip, round_trip=None).status_code == 422
