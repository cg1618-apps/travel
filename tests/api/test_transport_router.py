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


def test_departures_read_back_by_day_type_then_time(client, option):
    # Inserted out of order and across both day types.
    add_departure(client, option, day_type="holiday", time="13:40")
    add_departure(client, option, day_type="weekday", time="09:00")
    add_departure(client, option, day_type="holiday", time="07:30")
    departures = client.get("/api/transport-routes").json()[0]["options"][0]["departures"]
    assert [(d["day_type"], d["time"]) for d in departures] == [
        ("holiday", "07:30:00"),
        ("holiday", "13:40:00"),
        ("weekday", "09:00:00"),
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


def test_options_append_in_order_within_their_own_route(client, route, option):
    other = client.post("/api/transport-routes", json={"from_place": "台中", "to_place": "鹿港"}).json()
    second = client.post(
        f"/api/transport-routes/{route['id']}/options", json={"mode": "彰化客運6912"}
    ).json()
    assert second["position"] == option["position"] + 1
    # Positions are scoped to the route: a fresh route starts from the top.
    first_elsewhere = client.post(
        f"/api/transport-routes/{other['id']}/options", json={"mode": "台灣好行"}
    ).json()
    assert first_elsewhere["position"] == option["position"]


def test_a_null_for_a_required_field_is_a_422(client, route, option):
    option_url = f"/api/transport-options/{option['id']}"
    route_url = f"/api/transport-routes/{route['id']}"
    assert client.patch(option_url, json={"mode": None}).status_code == 422
    assert client.patch(route_url, json={"from_place": None}).status_code == 422
    # Mirror: a nullable field accepts null and clears.
    cleared = client.patch(option_url, json={"notes": None})
    assert cleared.status_code == 200 and cleared.json()["notes"] is None


def test_a_null_departure_time_is_a_422(client, option):
    departure = add_departure(client, option).json()
    url = f"/api/transport-departures/{departure['id']}"
    assert client.patch(url, json={"time": None}).status_code == 422
    # Mirror: a real time is accepted.
    assert client.patch(url, json={"time": "14:00"}).status_code == 200


def test_a_patch_that_changes_only_irregular_is_not_its_own_collision(client, option):
    departure = add_departure(client, option).json()
    response = client.patch(f"/api/transport-departures/{departure['id']}", json={"irregular": True})
    assert response.status_code == 200 and response.json()["irregular"] is True


def test_a_patch_onto_a_free_time_is_a_200(client, option):
    add_departure(client, option, time="07:00")
    later = add_departure(client, option, time="08:00").json()
    response = client.patch(f"/api/transport-departures/{later['id']}", json={"time": "09:00"})
    assert response.status_code == 200 and response.json()["time"] == "09:00:00"


def test_a_missing_route_option_or_departure_is_a_404(client, route, option):
    assert client.get("/api/transport-routes/0").status_code == 404
    assert client.post("/api/transport-routes/0/options", json={"mode": "x"}).status_code == 404
    assert client.patch("/api/transport-options/0", json={"notes": "x"}).status_code == 404
    assert client.delete("/api/transport-departures/0").status_code == 404
    # Mirror: the same calls on rows that exist do not 404.
    assert client.get(f"/api/transport-routes/{route['id']}").status_code == 200
    assert client.patch(f"/api/transport-options/{option['id']}", json={"notes": "x"}).status_code == 200


def test_an_option_patch_answers_with_its_departures(client, option):
    add_departure(client, option, time="07:30")
    response = client.patch(f"/api/transport-options/{option['id']}", json={"price": 30})
    assert response.json()["price"] == 30
    assert [d["time"] for d in response.json()["departures"]] == ["07:30:00"]


def test_deleting_an_option_takes_its_departures_and_keeps_the_route(
    client, db_session, route, option
):
    from app.models import TransportDeparture

    add_departure(client, option)
    assert client.delete(f"/api/transport-options/{option['id']}").status_code == 204
    assert db_session.query(TransportDeparture).count() == 0
    assert client.get(f"/api/transport-routes/{route['id']}").json()["options"] == []
