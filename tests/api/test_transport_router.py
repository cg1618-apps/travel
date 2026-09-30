"""Transport: routes own options, options own departures, and times are rows."""

import pytest


@pytest.fixture
def route(client):
    return client.post(
        "/api/transport-routes", json={"from_place": "彰化火車站", "to_place": "宿舍"}
    ).json()


@pytest.fixture
def option(client, route):
    return client.post(
        f"/api/transport-routes/{route['id']}/options",
        json={"mode": "彰化客運6933A", "board_at": "彰化", "alight_at": "南瑤宮", "price": 22},
    ).json()


def add_departure(client, option, **fields):
    payload = {"day_type": "holiday", "time": "13:40", **fields}
    return client.post(f"/api/transport-options/{option['id']}/departures", json=payload)


def test_a_route_reads_back_with_its_options_and_departures(client, route, option):
    add_departure(client, option, time="07:30")
    add_departure(client, option, time="13:40", irregular=True)
    routes = client.get("/api/transport-routes").json()
    assert [r["from_place"] for r in routes] == ["彰化火車站"]
    opt = routes[0]["options"][0]
    assert opt["mode"] == "彰化客運6933A" and opt["price"] == 22
    assert [(d["time"], d["irregular"]) for d in opt["departures"]] == [
        ("07:30:00", False),
        ("13:40:00", True),
    ]


def test_a_route_without_options_is_allowed(client, route):
    assert client.get(f"/api/transport-routes/{route['id']}").json()["options"] == []


def test_an_option_needs_a_mode(client, route):
    response = client.post(f"/api/transport-routes/{route['id']}/options", json={"mode": ""})
    assert response.status_code == 422


def test_an_unknown_day_type_is_a_422(client, option):
    assert add_departure(client, option, day_type="sunday").status_code == 422
    # Mirror.
    assert add_departure(client, option, day_type="weekday").status_code == 201


def test_a_duplicate_departure_is_a_409(client, option):
    assert add_departure(client, option).status_code == 201
    assert add_departure(client, option).status_code == 409
    # Mirror: same time, other day type, is a different departure.
    assert add_departure(client, option, day_type="weekday").status_code == 201


def test_a_patch_that_collides_is_a_409(client, option):
    add_departure(client, option, time="07:00")
    later = add_departure(client, option, time="08:00").json()
    response = client.patch(f"/api/transport-departures/{later['id']}", json={"time": "07:00"})
    assert response.status_code == 409


def test_deleting_a_route_takes_its_options_and_departures(client, db_session, route, option):
    from app.models import TransportDeparture, TransportOption

    add_departure(client, option)
    assert client.delete(f"/api/transport-routes/{route['id']}").status_code == 204
    assert db_session.query(TransportOption).count() == 0
    assert db_session.query(TransportDeparture).count() == 0


def test_options_append_in_order(client, route, option):
    second = client.post(
        f"/api/transport-routes/{route['id']}/options", json={"mode": "彰化客運6912"}
    ).json()
    assert second["position"] == option["position"] + 1
