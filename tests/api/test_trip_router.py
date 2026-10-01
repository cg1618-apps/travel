"""Trips: legs, the current-trip rule, and the date a linked list takes."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models import Trip, TripLeg
from app.services.domain.trip import current_trip

TPE = "+08:00"


def leg_payload(departs, arrives, **fields):
    return {"from_place": "彰化火車站", "to_place": "台北車站",
            "departs_at": departs, "arrives_at": arrives, **fields}


@pytest.fixture
def trip(client):
    return client.post("/api/trips", json={"name": "彰化 ⇄ 台北"}).json()


def add_leg(client, trip, departs=f"2026-09-24T18:06:00{TPE}", arrives=f"2026-09-24T20:59:00{TPE}", **fields):
    return client.post(f"/api/trips/{trip['id']}/legs", json=leg_payload(departs, arrives, **fields))


def test_a_leg_reads_back_with_its_booking(client, trip):
    response = add_leg(client, trip, service="火車 - 自強", service_number="5158", seat="5車15號",
                       price=550, ticket_type="電子", booked=True, paid=True, collected=True,
                       booking_code="0589115")
    assert response.status_code == 201
    body = client.get(f"/api/trips/{trip['id']}").json()["legs"][0]
    assert body["booking_code"] == "0589115"  # leading zero survives
    assert (body["booked"], body["paid"], body["collected"]) == (True, True, True)


def test_arriving_before_departing_is_a_422(client, trip):
    bad = add_leg(client, trip, departs=f"2026-09-24T20:00:00{TPE}", arrives=f"2026-09-24T19:00:00{TPE}")
    assert bad.status_code == 422
    assert add_leg(client, trip).status_code == 201  # mirror


def test_a_naive_time_is_a_422(client, trip):
    assert add_leg(client, trip, departs="2026-09-24T18:06:00", arrives="2026-09-24T20:59:00").status_code == 422


def test_a_list_can_be_linked_from_only_one_leg(client, trip):
    lst = client.post("/api/packing-lists", json={"name": "彰化回台北", "saved": True}).json()
    assert add_leg(client, trip, packing_list_id=lst["id"]).status_code == 201
    second = add_leg(client, trip, departs=f"2026-09-28T12:15:00{TPE}",
                     arrives=f"2026-09-28T14:23:00{TPE}", packing_list_id=lst["id"])
    assert second.status_code == 409
    # Mirror: the same leg without the link is fine.
    assert add_leg(client, trip, departs=f"2026-09-28T12:15:00{TPE}",
                   arrives=f"2026-09-28T14:23:00{TPE}").status_code == 201


def test_linking_a_missing_list_is_a_404(client, trip):
    assert add_leg(client, trip, packing_list_id=999999).status_code == 404


def test_a_linked_list_takes_the_taipei_date_of_its_leg(client, trip):
    lst = client.post("/api/packing-lists",
                      json={"name": "l", "saved": True, "departure_at": "2026-01-01"}).json()
    # 00:30 in Taipei is 16:30 the previous day in UTC: this is the case that
    # makes the timezone bite.
    add_leg(client, trip, departs=f"2026-09-24T00:30:00{TPE}", arrives=f"2026-09-24T03:00:00{TPE}",
            packing_list_id=lst["id"])
    body = client.get(f"/api/packing-lists/{lst['id']}").json()
    assert body["departure_at"] == "2026-09-24"
    assert body["departure_source"] == "trip_leg"


def test_an_unlinked_list_keeps_its_own_date(client):
    lst = client.post("/api/packing-lists",
                      json={"name": "l", "saved": True, "departure_at": "2026-01-01"}).json()
    body = client.get(f"/api/packing-lists/{lst['id']}").json()
    assert (body["departure_at"], body["departure_source"]) == ("2026-01-01", "list")


def test_deleting_a_linked_list_keeps_the_leg(client, trip):
    lst = client.post("/api/packing-lists", json={"name": "l", "saved": True}).json()
    leg = add_leg(client, trip, packing_list_id=lst["id"]).json()
    assert client.delete(f"/api/packing-lists/{lst['id']}").status_code == 204
    legs = client.get(f"/api/trips/{trip['id']}").json()["legs"]
    assert [(row["id"], row["packing_list_id"]) for row in legs] == [(leg["id"], None)]


def test_a_legs_ticket_type_is_remembered(client, trip):
    add_leg(client, trip, ticket_type="電子")
    values = [row["value"] for row in client.get("/api/label-options?kind=ticket_type").json()]
    assert values == ["電子"]


# --------------------------------------------------------------------------
# The current trip
# --------------------------------------------------------------------------

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


def make_trip(db, name, *offsets_hours):
    trip = Trip(name=name)
    db.add(trip)
    db.flush()
    for hours in offsets_hours:
        start = NOW + timedelta(hours=hours)
        db.add(TripLeg(trip_id=trip.id, from_place="a", to_place="b",
                       departs_at=start, arrives_at=start + timedelta(hours=1)))
    db.flush()
    return trip


def test_there_is_no_current_trip_without_legs(db_session):
    make_trip(db_session, "empty")
    assert current_trip(db_session, NOW) is None


def test_a_future_trip_beats_a_past_one(db_session):
    make_trip(db_session, "past", -48)
    future = make_trip(db_session, "future", 72)
    assert current_trip(db_session, NOW).id == future.id


def test_the_soonest_future_leg_wins(db_session):
    make_trip(db_session, "later", 72)
    sooner = make_trip(db_session, "sooner", -100, 24)  # has a past leg too
    assert current_trip(db_session, NOW).id == sooner.id


def test_with_nothing_ahead_the_most_recent_past_trip_wins(db_session):
    make_trip(db_session, "older", -200)
    recent = make_trip(db_session, "recent", -300, -10)
    assert current_trip(db_session, NOW).id == recent.id


def test_a_tie_goes_to_the_newer_trip(db_session):
    make_trip(db_session, "first", 24)
    second = make_trip(db_session, "second", 24)
    assert current_trip(db_session, NOW).id == second.id


def test_the_current_endpoint_is_404_when_there_is_none(client):
    response = client.get("/api/trips/current")
    assert response.status_code == 404
    assert response.json()["detail"] == "No current trip."


# --------------------------------------------------------------------------
# Updates, nulls, missing rows
# --------------------------------------------------------------------------


def test_a_patch_that_keeps_its_own_list_link_is_not_a_collision(client, trip):
    lst = client.post("/api/packing-lists", json={"name": "l", "saved": True}).json()
    leg = add_leg(client, trip, packing_list_id=lst["id"]).json()
    response = client.patch(
        f"/api/trip-legs/{leg['id']}", json={"packing_list_id": lst["id"], "seat": "1A"}
    )
    assert response.status_code == 200
    assert response.json()["seat"] == "1A"


def test_a_patch_onto_another_legs_list_is_a_409(client, trip):
    lst = client.post("/api/packing-lists", json={"name": "l", "saved": True}).json()
    add_leg(client, trip, packing_list_id=lst["id"])
    other = add_leg(
        client, trip, departs=f"2026-09-28T12:15:00{TPE}", arrives=f"2026-09-28T14:23:00{TPE}"
    ).json()
    bad = client.patch(f"/api/trip-legs/{other['id']}", json={"packing_list_id": lst["id"]})
    assert bad.status_code == 409
    assert bad.json()["detail"] == "That packing list is already linked to another leg."
    assert client.patch(f"/api/trip-legs/{other['id']}", json={"seat": "2B"}).status_code == 200


def test_a_patch_can_unlink_a_list(client, trip):
    lst = client.post("/api/packing-lists", json={"name": "l", "saved": True}).json()
    leg = add_leg(client, trip, packing_list_id=lst["id"]).json()
    response = client.patch(f"/api/trip-legs/{leg['id']}", json={"packing_list_id": None})
    assert response.status_code == 200
    assert response.json()["packing_list_id"] is None


def test_a_leg_response_names_its_list(client, trip):
    lst = client.post("/api/packing-lists", json={"name": "彰化回台北", "saved": True}).json()
    leg = add_leg(client, trip, packing_list_id=lst["id"]).json()
    assert leg["packing_list_name"] == "彰化回台北"


def test_a_patch_moving_arrival_before_departure_is_a_422(client, trip):
    leg = add_leg(client, trip).json()
    bad = client.patch(f"/api/trip-legs/{leg['id']}", json={"arrives_at": f"2026-09-24T10:00:00{TPE}"})
    assert bad.status_code == 422
    good = client.patch(f"/api/trip-legs/{leg['id']}", json={"arrives_at": f"2026-09-24T22:00:00{TPE}"})
    assert good.status_code == 200


def test_a_null_for_a_required_leg_field_is_a_422(client, trip):
    leg = add_leg(client, trip, notes="x").json()
    assert client.patch(f"/api/trip-legs/{leg['id']}", json={"from_place": None}).status_code == 422
    assert client.patch(f"/api/trip-legs/{leg['id']}", json={"notes": None}).status_code == 200


def test_a_null_for_a_trips_name_is_a_422(client, trip):
    assert client.patch(f"/api/trips/{trip['id']}", json={"name": None}).status_code == 422
    assert client.patch(f"/api/trips/{trip['id']}", json={"notes": None}).status_code == 200


def test_a_missing_trip_or_leg_is_a_404(client, trip):
    leg = add_leg(client, trip).json()
    assert client.get("/api/trips/999999").status_code == 404
    assert client.patch("/api/trips/999999", json={"name": "x"}).status_code == 404
    assert client.delete("/api/trips/999999").status_code == 404
    assert client.post("/api/trips/999999/legs", json=leg_payload(
        f"2026-09-24T18:06:00{TPE}", f"2026-09-24T20:59:00{TPE}")).status_code == 404
    assert client.patch("/api/trip-legs/999999", json={"seat": "x"}).status_code == 404
    assert client.delete("/api/trip-legs/999999").status_code == 404
    # Mirror: the rows that do exist answer.
    assert client.get(f"/api/trips/{trip['id']}").status_code == 200
    assert client.patch(f"/api/trip-legs/{leg['id']}", json={"seat": "x"}).status_code == 200


def test_deleting_a_trip_deletes_its_legs(client, trip):
    leg = add_leg(client, trip).json()
    assert client.delete(f"/api/trips/{trip['id']}").status_code == 204
    assert client.patch(f"/api/trip-legs/{leg['id']}", json={"seat": "x"}).status_code == 404


def test_trips_list_newest_latest_departure_first_and_legless_last(client):
    old = client.post("/api/trips", json={"name": "old"}).json()
    new = client.post("/api/trips", json={"name": "new"}).json()
    client.post("/api/trips", json={"name": "empty"})
    add_leg(client, old, departs=f"2026-01-01T10:00:00{TPE}", arrives=f"2026-01-01T11:00:00{TPE}")
    add_leg(client, new, departs=f"2026-06-01T10:00:00{TPE}", arrives=f"2026-06-01T11:00:00{TPE}")
    names = [row["name"] for row in client.get("/api/trips").json()]
    assert names == ["new", "old", "empty"]


def test_the_current_endpoint_returns_the_trip_when_there_is_one(client, trip):
    far = datetime.now(timezone.utc) + timedelta(days=30)
    add_leg(client, trip, departs=far.isoformat(), arrives=(far + timedelta(hours=2)).isoformat())
    response = client.get("/api/trips/current")
    assert response.status_code == 200
    assert response.json()["id"] == trip["id"]
    assert response.json()["legs"]


def test_a_trip_defaults_to_private(db_session):
    trip = Trip(name="彰化 ⇄ 台北")
    db_session.add(trip)
    db_session.flush()
    db_session.refresh(trip)
    assert trip.visibility == "private"


def test_an_unknown_trip_visibility_is_refused_by_the_database(db_session):
    from sqlalchemy.exc import IntegrityError

    db_session.add(Trip(name="彰化 ⇄ 台北", visibility="friends"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_every_declared_trip_visibility_is_accepted(db_session):
    # The mirror of the refusal above, with the same shape of row.
    from app.constants import Visibility

    for visibility in Visibility:
        db_session.add(Trip(name=f"trip {visibility}", visibility=visibility))
    db_session.flush()


def test_a_leg_patch_remembers_its_ticket_type(client, trip):
    leg = add_leg(client, trip).json()
    assert client.patch(f"/api/trip-legs/{leg['id']}", json={"ticket_type": "紙本"}).status_code == 200
    values = [row["value"] for row in client.get("/api/label-options?kind=ticket_type").json()]
    assert values == ["紙本"]


# --------------------------------------------------------------------------
# Archive and template flags
# --------------------------------------------------------------------------


def test_a_new_trip_is_neither_archived_nor_a_template(client, trip):
    assert (trip["archived"], trip["archive_note"], trip["template"]) == (False, None, False)


def test_a_trip_can_be_archived_with_a_remark_and_unarchived(client, trip):
    url = f"/api/trips/{trip['id']}"
    body = client.patch(url, json={"archived": True, "archive_note": "下次早點訂票"}).json()
    assert (body["archived"], body["archive_note"]) == (True, "下次早點訂票")
    body = client.patch(url, json={"archived": False}).json()
    # Un-archiving leaves the remark alone.
    assert (body["archived"], body["archive_note"]) == (False, "下次早點訂票")
    assert client.patch(url, json={"archive_note": None}).json()["archive_note"] is None


def test_a_trip_can_be_made_a_template_and_back(client, trip):
    url = f"/api/trips/{trip['id']}"
    assert client.patch(url, json={"template": True}).json()["template"] is True
    assert client.patch(url, json={"template": False}).json()["template"] is False


@pytest.mark.parametrize("field", ["archived", "template"])
def test_a_null_archive_or_template_flag_is_a_422(client, trip, field):
    assert client.patch(f"/api/trips/{trip['id']}", json={field: None}).status_code == 422
