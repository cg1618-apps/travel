"""Trips: legs, the four shelves, and the date a linked list takes."""

from datetime import datetime, timedelta, timezone

import pytest

from app.constants import Kind, Usage
from app.models import Trip, TripLeg

TPE = "+08:00"
NOW = datetime(2026, 9, 25, tzinfo=timezone.utc)


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
    lst = client.post("/api/packing-lists", json={"name": "彰化回台北", "kind": "template"}).json()
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
                      json={"name": "l", "kind": "template", "departure_at": "2026-01-01"}).json()
    # 00:30 in Taipei is 16:30 the previous day in UTC: this is the case that
    # makes the timezone bite.
    add_leg(client, trip, departs=f"2026-09-24T00:30:00{TPE}", arrives=f"2026-09-24T03:00:00{TPE}",
            packing_list_id=lst["id"])
    body = client.get(f"/api/packing-lists/{lst['id']}").json()
    assert body["departure_at"] == "2026-09-24"
    assert body["departure_source"] == "trip_leg"


def test_an_unlinked_list_keeps_its_own_date(client):
    lst = client.post("/api/packing-lists",
                      json={"name": "l", "kind": "template", "departure_at": "2026-01-01"}).json()
    body = client.get(f"/api/packing-lists/{lst['id']}").json()
    assert (body["departure_at"], body["departure_source"]) == ("2026-01-01", "list")


def test_deleting_a_linked_list_keeps_the_leg(client, trip):
    lst = client.post("/api/packing-lists", json={"name": "l", "kind": "template"}).json()
    leg = add_leg(client, trip, packing_list_id=lst["id"]).json()
    assert client.delete(f"/api/packing-lists/{lst['id']}").status_code == 204
    legs = client.get(f"/api/trips/{trip['id']}").json()["legs"]
    assert [(row["id"], row["packing_list_id"]) for row in legs] == [(leg["id"], None)]


def test_a_legs_ticket_type_is_remembered(client, trip):
    add_leg(client, trip, ticket_type="電子")
    values = [row["value"] for row in client.get("/api/label-options?kind=ticket_type").json()]
    assert values == ["電子"]


# --------------------------------------------------------------------------
# Updates, nulls, missing rows
# --------------------------------------------------------------------------


def test_a_patch_that_keeps_its_own_list_link_is_not_a_collision(client, trip):
    lst = client.post("/api/packing-lists", json={"name": "l", "kind": "template"}).json()
    leg = add_leg(client, trip, packing_list_id=lst["id"]).json()
    response = client.patch(
        f"/api/trip-legs/{leg['id']}", json={"packing_list_id": lst["id"], "seat": "1A"}
    )
    assert response.status_code == 200
    assert response.json()["seat"] == "1A"


def test_a_patch_onto_another_legs_list_is_a_409(client, trip):
    lst = client.post("/api/packing-lists", json={"name": "l", "kind": "template"}).json()
    add_leg(client, trip, packing_list_id=lst["id"])
    other = add_leg(
        client, trip, departs=f"2026-09-28T12:15:00{TPE}", arrives=f"2026-09-28T14:23:00{TPE}"
    ).json()
    bad = client.patch(f"/api/trip-legs/{other['id']}", json={"packing_list_id": lst["id"]})
    assert bad.status_code == 409
    assert bad.json()["detail"] == "That packing list is already linked to another leg."
    assert client.patch(f"/api/trip-legs/{other['id']}", json={"seat": "2B"}).status_code == 200


def test_a_patch_can_unlink_a_list(client, trip):
    lst = client.post("/api/packing-lists", json={"name": "l", "kind": "template"}).json()
    leg = add_leg(client, trip, packing_list_id=lst["id"]).json()
    response = client.patch(f"/api/trip-legs/{leg['id']}", json={"packing_list_id": None})
    assert response.status_code == 200
    assert response.json()["packing_list_id"] is None


def test_a_leg_response_names_its_list(client, trip):
    lst = client.post("/api/packing-lists", json={"name": "彰化回台北", "kind": "template"}).json()
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
# Shelves, usage and bulk delete
# --------------------------------------------------------------------------


def a_trip(db_session, name, usage=Usage.UNUSED, legs=(), created=0, **fields):
    # `created_at` is explicit: `now()` is the transaction's start, so trips
    # made in one test would otherwise tie. `usage=None` is left to the
    # column default (None for a saved or template kind) rather than passed.
    if usage is not None:
        fields["usage"] = usage
    trip = Trip(name=name, created_at=NOW + timedelta(days=created), **fields)
    for days in legs:
        departs = NOW + timedelta(days=days)
        trip.legs.append(TripLeg(from_place="a", to_place="b", departs_at=departs,
                                 arrives_at=departs + timedelta(hours=1)))
    db_session.add(trip)
    db_session.flush()
    return trip


def test_there_is_no_current_trip_endpoint(client, trip):
    # It falls to /api/trips/{trip_id}, whose int path refuses "current".
    assert client.get("/api/trips/current").status_code == 422
    assert client.get(f"/api/trips/{trip['id']}").status_code == 200  # mirror


@pytest.mark.parametrize("usage", [Usage.IN_USE, Usage.UPCOMING, Usage.UNUSED])
def test_every_trip_is_on_exactly_one_shelf(client, db_session, usage):
    """The regression for the lone trip no section showed. The one-row case
    is the production one: a single 一般 trip must be on 一般."""
    a_trip(db_session, "only", usage, legs=[1])
    db_session.commit()
    body = client.get("/api/trips").json()
    assert [t["name"] for t in body["free"]] == ["only"]
    a_trip(db_session, "auto", Usage.PAST, auto_saved_at=NOW, created=1)
    a_trip(db_session, "kept", None, kind=Kind.SAVED, created=2)
    a_trip(db_session, "tpl", None, kind=Kind.TEMPLATE, created=3)
    db_session.commit()
    body = client.get("/api/trips").json()
    shown = [t["name"] for shelf in ("free", "auto_saved", "saved", "templates") for t in body[shelf]]
    assert sorted(shown) == ["auto", "kept", "only", "tpl"]


def test_shelves_are_newest_created_first_and_carry_created_at(client, db_session):
    a_trip(db_session, "older", legs=[9], created=0)
    a_trip(db_session, "newer", created=1)
    db_session.commit()
    free = client.get("/api/trips").json()["free"]
    assert [t["name"] for t in free] == ["newer", "older"]
    assert free[0]["created_at"].startswith("2026-09-26")


def test_the_index_has_four_shelves(client, db_session):
    a_trip(db_session, "free")
    a_trip(db_session, "auto", Usage.PAST, auto_saved_at=NOW)
    a_trip(db_session, "kept", None, kind=Kind.SAVED)
    a_trip(db_session, "tpl", None, kind=Kind.TEMPLATE)
    db_session.commit()
    body = client.get("/api/trips").json()
    assert {name: [t["name"] for t in body[name]] for name in ("free", "auto_saved", "saved", "templates")} \
        == {"free": ["free"], "auto_saved": ["auto"], "saved": ["kept"], "templates": ["tpl"]}
    assert body["evict_next"] == []


@pytest.fixture
def ten_auto_saved(db_session):
    """The trip queue at its limit. Load-bearing."""
    rows = [a_trip(db_session, f"T{d}", Usage.PAST, auto_saved_at=NOW + timedelta(days=d)) for d in range(10)]
    db_session.commit()
    return rows


def test_past_when_ten_are_auto_saved_is_a_409(ten_auto_saved, client, trip):
    refused = client.patch(f"/api/trips/{trip['id']}", json={"usage": "past"})
    assert refused.status_code == 409
    assert "T0" in refused.json()["detail"]
    assert client.get("/api/trips").json()["evict_next"][0]["name"] == "T0"


def test_past_confirmed_drops_the_oldest_trip(ten_auto_saved, client, db_session, trip):
    oldest = ten_auto_saved[0].id
    body = client.patch(f"/api/trips/{trip['id']}", json={"usage": "past", "evict_confirmed": True}).json()
    assert body["usage"] == "past"
    db_session.expire_all()
    assert db_session.get(Trip, oldest) is None


def test_past_with_room_is_not_refused(ten_auto_saved, client, db_session, trip):
    db_session.delete(ten_auto_saved[-1])
    db_session.commit()
    assert client.patch(f"/api/trips/{trip['id']}", json={"usage": "past"}).status_code == 200


def test_saving_a_trip_keeps_its_archive_note(client, trip):
    url = f"/api/trips/{trip['id']}"
    body = client.patch(url, json={"kind": "saved", "archive_note": "下次早點訂票"}).json()
    assert (body["kind"], body["usage"], body["archive_note"]) == ("saved", None, "下次早點訂票")
    body = client.patch(url, json={"kind": "free"}).json()
    assert (body["kind"], body["usage"], body["archive_note"]) == ("free", "unused", "下次早點訂票")


@pytest.mark.parametrize("payload", [{"kind": "template"}, {"kind": None}, {"usage": None}])
def test_a_trip_refuses_impossible_moves(client, trip, payload):
    assert client.patch(f"/api/trips/{trip['id']}", json=payload).status_code == 422


def test_a_trip_template_can_be_created(client):
    body = client.post("/api/trips", json={"name": "x", "kind": "template"}).json()
    assert (body["kind"], body["usage"]) == ("template", None)


def test_bulk_delete_deletes_every_named_trip(client, db_session):
    rows = [a_trip(db_session, f"t{i}") for i in range(3)]
    db_session.commit()
    ids = [rows[0].id, rows[1].id, rows[1].id]  # a duplicate is deleted once
    assert client.post("/api/trips/bulk-delete", json={"ids": ids}).status_code == 204
    db_session.expire_all()
    assert [db_session.get(Trip, row.id) is None for row in rows] == [True, True, False]


def test_bulk_delete_with_a_missing_id_deletes_nothing(client, db_session):
    row = a_trip(db_session, "t")
    db_session.commit()
    response = client.post("/api/trips/bulk-delete", json={"ids": [row.id, 999999]})
    assert response.status_code == 404
    db_session.expire_all()
    assert db_session.get(Trip, row.id) is not None


def test_bulk_delete_of_nothing_is_a_204(client):
    assert client.post("/api/trips/bulk-delete", json={"ids": []}).status_code == 204
