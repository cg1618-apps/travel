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


# --- ordering routes ------------------------------------------------------------


def add_route(client, from_place, to_place="宿舍"):
    return client.post(
        "/api/transport-routes", json={"from_place": from_place, "to_place": to_place}
    ).json()


@pytest.fixture
def three_routes(client):
    """Three routes at positions 0..2. Load-bearing for every refusal below:
    an order over an empty set would have nothing to refuse."""
    routes = [add_route(client, name) for name in ("台中", "彰化", "鹿港")]
    assert [r["position"] for r in routes] == [0, 1, 2]
    return [r["id"] for r in routes]


def route_order(client):
    return [r["id"] for r in client.get("/api/transport-routes").json()]


def put_route_order(client, route_ids):
    return client.put("/api/transport-routes/order", json={"route_ids": route_ids})


def test_route_order_sets_positions_and_returns_every_route(client, three_routes):
    a, b, c = three_routes
    response = put_route_order(client, [c, a, b])
    assert response.status_code == 200
    body = response.json()
    assert [r["id"] for r in body] == [c, a, b]
    assert [r["position"] for r in body] == [0, 1, 2]
    assert route_order(client) == [c, a, b]


def test_route_order_missing_a_route_is_refused(client, three_routes):
    a, b, c = three_routes
    response = put_route_order(client, [c, a])
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert route_order(client) == [a, b, c]


def test_route_order_naming_a_route_twice_is_refused(client, three_routes):
    a, b, c = three_routes
    # Same length as the set, so only the duplicate check can refuse it.
    response = put_route_order(client, [c, c, a])
    assert response.status_code == 422
    assert route_order(client) == [a, b, c]


def test_route_order_naming_an_unknown_route_is_refused(client, three_routes):
    a, b, c = three_routes
    response = put_route_order(client, [c, a, b, 999999])
    assert response.status_code == 422
    assert route_order(client) == [a, b, c]


def test_route_order_of_no_routes_is_accepted(client):
    response = put_route_order(client, [])
    assert response.status_code == 200 and response.json() == []


def test_the_order_path_is_not_read_as_a_route_id(client, three_routes):
    # Registered as /{route_id}, "order" would be a 422 for a non-integer id
    # whatever the body; registered on its own, a body naming every route is a 200.
    assert put_route_order(client, three_routes).status_code == 200
    assert client.get(f"/api/transport-routes/{three_routes[0]}").status_code == 200


# --- ordering the options of a route --------------------------------------------


def add_option(client, route, mode):
    return client.post(f"/api/transport-routes/{route['id']}/options", json={"mode": mode}).json()


@pytest.fixture
def three_options(client, route):
    """Three options on one route. Load-bearing, as with `three_routes`."""
    return [add_option(client, route, mode)["id"] for mode in ("公車", "火車", "高鐵")]


def option_order(client, route):
    return [o["id"] for o in client.get(f"/api/transport-routes/{route['id']}").json()["options"]]


def put_option_order(client, route, option_ids):
    return client.put(
        f"/api/transport-routes/{route['id']}/order", json={"option_ids": option_ids}
    )


def test_option_order_sets_positions_and_returns_the_route(client, route, three_options):
    a, b, c = three_options
    response = put_option_order(client, route, [b, c, a])
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == route["id"]
    assert [o["id"] for o in body["options"]] == [b, c, a]
    assert [o["position"] for o in body["options"]] == [0, 1, 2]
    assert option_order(client, route) == [b, c, a]


def test_option_order_missing_an_option_is_refused(client, route, three_options):
    a, b, c = three_options
    assert put_option_order(client, route, [c, a]).status_code == 422
    assert option_order(client, route) == [a, b, c]


def test_option_order_naming_an_option_twice_is_refused(client, route, three_options):
    a, b, c = three_options
    assert put_option_order(client, route, [c, c, a]).status_code == 422
    assert option_order(client, route) == [a, b, c]


def test_option_order_naming_another_routes_option_is_refused(client, route, three_options):
    a, b, c = three_options
    other = add_route(client, "台北")
    foreign = add_option(client, other, "客運")["id"]
    response = put_option_order(client, route, [c, b, a, foreign])
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert option_order(client, route) == [a, b, c]
    assert option_order(client, other) == [foreign]


def test_option_order_on_an_unknown_route_is_a_404(client):
    response = client.put("/api/transport-routes/999999/order", json={"option_ids": []})
    assert response.status_code == 404


def test_option_order_of_a_route_without_options_is_accepted(client, route):
    assert put_option_order(client, route, []).status_code == 200


# --- notes on a route ---------------------------------------------------------------


def add_note(client, route, **fields):
    return client.post(f"/api/transport-routes/{route['id']}/notes", json=fields)


def test_a_note_reads_back_with_its_links_in_order(client, route):
    response = add_note(
        client, route, title="轉乘", description="在彰化換車",
        links=["https://example.invalid/b", "https://example.invalid/a"],
    )
    assert response.status_code == 201
    note = response.json()
    assert (note["route_id"], note["title"], note["description"]) == (route["id"], "轉乘", "在彰化換車")
    assert note["links"] == ["https://example.invalid/b", "https://example.invalid/a"]
    entries = client.get(f"/api/transport-routes/{route['id']}").json()["note_entries"]
    assert entries == [note]


def test_the_route_notes_text_is_untouched_by_note_entries(client, route):
    client.patch(f"/api/transport-routes/{route['id']}", json={"notes": "走路也行"})
    add_note(client, route, title="轉乘")
    body = client.get(f"/api/transport-routes/{route['id']}").json()
    assert body["notes"] == "走路也行"
    assert [n["title"] for n in body["note_entries"]] == ["轉乘"]


def test_notes_append_in_order_within_their_own_route(client, route):
    first = add_note(client, route, title="一").json()
    second = add_note(client, route, title="二").json()
    assert (first["position"], second["position"]) == (0, 1)
    other = add_route(client, "台北")
    assert add_note(client, other, title="三").json()["position"] == 0
    entries = client.get(f"/api/transport-routes/{route['id']}").json()["note_entries"]
    assert [n["title"] for n in entries] == ["一", "二"]


def test_every_route_read_carries_note_entries(client, route):
    add_note(client, route, title="轉乘")
    listed = client.get("/api/transport-routes").json()[0]
    assert [n["title"] for n in listed["note_entries"]] == ["轉乘"]
    patched = client.patch(f"/api/transport-routes/{route['id']}", json={"notes": "x"}).json()
    assert [n["title"] for n in patched["note_entries"]] == ["轉乘"]
    ordered = put_route_order(client, [route["id"]]).json()
    assert [n["title"] for n in ordered[0]["note_entries"]] == ["轉乘"]


def test_a_note_with_only_a_link_is_accepted(client, route):
    response = add_note(client, route, links=["https://example.invalid"])
    assert response.status_code == 201
    assert response.json()["title"] is None


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"description": "只有說明"},
        {"title": "   ", "links": []},
        {"title": None, "description": "x", "links": []},
    ],
)
def test_a_note_needs_a_title_or_a_link(client, route, body):
    response = add_note(client, route, **body)
    assert response.status_code == 422
    assert client.get(f"/api/transport-routes/{route['id']}").json()["note_entries"] == []


def test_a_title_is_stripped_and_a_blank_one_is_null(client, route):
    note = add_note(client, route, title="  轉乘  ", links=["https://example.invalid"]).json()
    assert note["title"] == "轉乘"
    blank = add_note(client, route, title="  ", links=["https://example.invalid"]).json()
    assert blank["title"] is None


def test_a_blank_link_is_a_422_not_dropped(client, route):
    response = add_note(client, route, title="轉乘", links=["https://example.invalid", "  "])
    assert response.status_code == 422
    # Mirror: the same note without the blank entry is accepted, links stripped.
    ok = add_note(client, route, title="轉乘", links=[" https://example.invalid "])
    assert ok.status_code == 201 and ok.json()["links"] == ["https://example.invalid"]


def test_a_note_on_an_unknown_route_is_a_404(client):
    response = client.post("/api/transport-routes/999999/notes", json={"title": "x"})
    assert response.status_code == 404


def test_patching_links_replaces_the_whole_list(client, route):
    note = add_note(client, route, title="轉乘", links=["https://a.invalid", "https://b.invalid"]).json()
    url = f"/api/transport-notes/{note['id']}"
    response = client.patch(url, json={"links": ["https://c.invalid", "https://a.invalid"]})
    assert response.status_code == 200
    assert response.json()["links"] == ["https://c.invalid", "https://a.invalid"]
    entries = client.get(f"/api/transport-routes/{route['id']}").json()["note_entries"]
    assert entries[0]["links"] == ["https://c.invalid", "https://a.invalid"]


def test_patching_without_links_keeps_them(client, route):
    note = add_note(client, route, title="轉乘", links=["https://a.invalid"]).json()
    response = client.patch(f"/api/transport-notes/{note['id']}", json={"description": "新"})
    assert response.status_code == 200
    assert (response.json()["description"], response.json()["links"]) == ("新", ["https://a.invalid"])


def test_link_rows_are_positioned_in_order(client, db_session, route):
    from app.models import TransportNoteLink

    note = add_note(client, route, title="t", links=["https://a.invalid", "https://b.invalid"]).json()
    client.patch(f"/api/transport-notes/{note['id']}",
                 json={"links": ["https://c.invalid", "https://d.invalid", "https://e.invalid"]})
    db_session.expire_all()
    rows = db_session.query(TransportNoteLink).order_by(TransportNoteLink.position).all()
    # The old rows are gone, not left behind with stale positions.
    assert [(r.url, r.position) for r in rows] == [
        ("https://c.invalid", 0), ("https://d.invalid", 1), ("https://e.invalid", 2),
    ]


def test_a_patch_that_leaves_neither_title_nor_link_is_refused(client, route):
    note = add_note(client, route, title="轉乘", links=["https://a.invalid"]).json()
    url = f"/api/transport-notes/{note['id']}"
    # Load-bearing: the note has BOTH, so removing one alone is fine...
    assert client.patch(url, json={"title": None}).status_code == 200
    # ...and removing the other as well is what the rule refuses.
    response = client.patch(url, json={"links": []})
    assert response.status_code == 422
    entry = client.get(f"/api/transport-routes/{route['id']}").json()["note_entries"][0]
    assert entry["links"] == ["https://a.invalid"]


def test_a_patch_removing_the_title_of_a_linkless_note_is_refused(client, route):
    note = add_note(client, route, title="轉乘", description="說明").json()
    url = f"/api/transport-notes/{note['id']}"
    assert client.patch(url, json={"title": "  "}).status_code == 422
    assert client.patch(url, json={"title": None}).status_code == 422
    # Mirror: a title and a link swapped in one patch is accepted.
    swapped = client.patch(url, json={"title": None, "links": ["https://a.invalid"]})
    assert swapped.status_code == 200 and swapped.json()["title"] is None


def test_a_blank_link_on_patch_is_a_422(client, route):
    note = add_note(client, route, title="轉乘").json()
    url = f"/api/transport-notes/{note['id']}"
    assert client.patch(url, json={"links": [""]}).status_code == 422
    # Mirror.
    assert client.patch(url, json={"links": ["https://a.invalid"]}).status_code == 200


def test_null_links_on_patch_is_a_422(client, route):
    note = add_note(client, route, title="轉乘").json()
    url = f"/api/transport-notes/{note['id']}"
    assert client.patch(url, json={"links": None}).status_code == 422


def test_deleting_a_note_takes_its_links(client, db_session, route):
    from app.models import TransportNote, TransportNoteLink

    note = add_note(client, route, title="t", links=["https://a.invalid"]).json()
    assert client.delete(f"/api/transport-notes/{note['id']}").status_code == 204
    assert db_session.query(TransportNote).count() == 0
    assert db_session.query(TransportNoteLink).count() == 0
    assert client.get(f"/api/transport-routes/{route['id']}").status_code == 200


def test_deleting_a_route_takes_its_notes_and_links(client, db_session, route):
    from app.models import TransportNote, TransportNoteLink

    add_note(client, route, title="t", links=["https://a.invalid"])
    assert client.delete(f"/api/transport-routes/{route['id']}").status_code == 204
    assert db_session.query(TransportNote).count() == 0
    assert db_session.query(TransportNoteLink).count() == 0


def test_a_missing_note_is_a_404(client, route):
    assert client.patch("/api/transport-notes/999999", json={"title": "x"}).status_code == 404
    assert client.delete("/api/transport-notes/999999").status_code == 404
    # Mirror.
    note = add_note(client, route, title="t").json()
    assert client.patch(f"/api/transport-notes/{note['id']}", json={"title": "x"}).status_code == 200


# --- ordering the notes of a route --------------------------------------------------


@pytest.fixture
def three_notes(client, route):
    """Three notes at positions 0..2. Load-bearing for the refusals below."""
    return [add_note(client, route, title=title).json()["id"] for title in ("一", "二", "三")]


def note_order(client, route):
    return [n["id"] for n in client.get(f"/api/transport-routes/{route['id']}").json()["note_entries"]]


def put_note_order(client, route, note_ids):
    return client.put(f"/api/transport-routes/{route['id']}/note-order", json={"note_ids": note_ids})


def test_note_order_sets_positions_and_returns_the_route(client, route, three_notes):
    a, b, c = three_notes
    response = put_note_order(client, route, [c, a, b])
    assert response.status_code == 200
    assert [n["id"] for n in response.json()["note_entries"]] == [c, a, b]
    assert note_order(client, route) == [c, a, b]


def test_note_order_missing_a_note_is_refused(client, route, three_notes):
    a, b, c = three_notes
    assert put_note_order(client, route, [c, a]).status_code == 422
    assert note_order(client, route) == [a, b, c]


def test_note_order_naming_another_routes_note_is_refused(client, route, three_notes):
    other = add_route(client, "台中")
    foreign = add_note(client, other, title="外").json()["id"]
    assert put_note_order(client, route, [*three_notes, foreign]).status_code == 422
    assert note_order(client, route) == three_notes


def test_note_order_on_an_unknown_route_is_a_404(client):
    response = client.put("/api/transport-routes/999999/note-order", json={"note_ids": []})
    assert response.status_code == 404


# --- route groups --------------------------------------------------------------------


def add_grouped(client, from_place, group=None):
    return client.post(
        "/api/transport-routes",
        json={"from_place": from_place, "to_place": "宿舍", "group_name": group},
    ).json()


def route_rows(client):
    return [(r["from_place"], r["group_name"], r["position"])
            for r in client.get("/api/transport-routes").json()]


@pytest.fixture
def grouped_routes(client):
    """彰化 ×2, ungrouped ×1, 台中 ×1: positions 0..3. Load-bearing: a group
    with something after it, and groups for a reorder to split."""
    ids = {name: add_grouped(client, name, group)["id"]
           for name, group in (("a", "彰化"), ("b", "彰化"), ("c", None), ("d", "台中"))}
    assert route_rows(client) == [("a", "彰化", 0), ("b", "彰化", 1), ("c", None, 2),
                                  ("d", "台中", 3)]
    return ids


def test_a_new_route_joins_the_end_of_its_group(client, grouped_routes):
    assert add_grouped(client, "e", "彰化")["position"] == 2
    assert [name for name, _, _ in route_rows(client)] == ["a", "b", "e", "c", "d"]


def test_a_blank_group_is_no_group(client, grouped_routes):
    assert add_grouped(client, "e", "  ")["group_name"] is None
    assert [name for name, _, _ in route_rows(client)] == ["a", "b", "c", "e", "d"]


def test_changing_a_routes_group_moves_it_to_the_end_of_that_group(client, grouped_routes):
    client.patch(f"/api/transport-routes/{grouped_routes['d']}", json={"group_name": "彰化"})
    assert [name for name, _, _ in route_rows(client)] == ["a", "b", "d", "c"]


def test_a_route_order_splitting_a_group_is_refused(client, grouped_routes):
    ids = grouped_routes
    refused = put_route_order(client, [ids["a"], ids["c"], ids["b"], ids["d"]])
    assert refused.status_code == 422
    assert refused.json()["detail"] == (
        'The order splits the "彰化" group: a group\'s routes must be adjacent.')
    assert [name for name, _, _ in route_rows(client)] == ["a", "b", "c", "d"]
    # Mirror: the same routes, groups kept whole.
    assert put_route_order(client, [ids["d"], ids["b"], ids["a"], ids["c"]]).status_code == 200
