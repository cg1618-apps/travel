"""Creating a trip from another: the definition carries, the state resets,
and the legs move to the chosen start date."""

from datetime import datetime

import pytest

TPE = "+08:00"


def at(value):
    """An instant, whatever offset the API chose to serialise it in."""
    return datetime.fromisoformat(value)


def make_source(client):
    """A source trip with every reset field SET, so a reset that fails to
    happen shows up: ticked, coded, seated, linked, saved with a remark."""
    source = client.post("/api/trips", json={"name": "範本", "notes": "帶身分證"}).json()
    lst = client.post("/api/packing-lists", json={"name": "台北去彰化"}).json()
    legs = [
        # Crosses Taipei midnight, and departs at 23:30 Taipei = 15:30 UTC.
        {"from_place": "台北車站", "to_place": "彰化火車站",
         "departs_at": f"2026-09-24T23:30:00{TPE}", "arrives_at": f"2026-09-25T01:10:00{TPE}",
         "service": "火車 - 自強", "service_number": "5158", "seat": "5車15號", "price": 550,
         "ticket_type": "電子", "booked": True, "paid": True, "collected": True,
         "booking_code": "0589115", "notes": "靠窗", "packing_list_id": lst["id"]},
        {"from_place": "彰化火車站", "to_place": "台北車站",
         "departs_at": f"2026-09-28T12:15:00{TPE}", "arrives_at": f"2026-09-28T14:23:00{TPE}",
         "booked": True, "booking_code": "1234567"},
    ]
    for leg in legs:
        assert client.post(f"/api/trips/{source['id']}/legs", json=leg).status_code == 201
    client.patch(f"/api/trips/{source['id']}",
                 json={"kind": "saved", "archive_note": "舊的"})
    return client.get(f"/api/trips/{source['id']}").json()


def trip_count(client):
    index = client.get("/api/trips").json()
    return sum(len(index[shelf]) for shelf in ("free", "auto_saved", "saved", "templates"))


def copy(client, source, **body):
    return client.post("/api/trips", json={"name": "新行程", "copy_from_id": source["id"], **body})


def test_the_definition_carries_and_the_state_resets(client):
    source = make_source(client)
    response = copy(client, source, start_date="2026-10-08")
    assert response.status_code == 201
    new = response.json()

    assert (new["name"], new["notes"]) == ("新行程", "帶身分證")
    assert (new["kind"], new["usage"], new["archive_note"]) == ("free", "unused", None)

    first, second = new["legs"]
    assert (first["from_place"], first["to_place"]) == ("台北車站", "彰化火車站")
    assert (first["service"], first["service_number"], first["price"], first["ticket_type"],
            first["notes"]) == ("火車 - 自強", "5158", 550, "電子", "靠窗")
    for leg in (first, second):
        assert (leg["booked"], leg["paid"], leg["collected"]) == (False, False, False)
        assert (leg["booking_code"], leg["seat"], leg["packing_list_id"]) == (None, None, None)
    assert {leg["trip_id"] for leg in new["legs"]} == {new["id"]}


def test_the_legs_move_to_the_start_date_keeping_clock_and_gaps(client):
    source = make_source(client)
    new = copy(client, source, start_date="2026-10-08").json()
    first, second = new["legs"]
    # Taipei day 09-24 → 10-08 is +14 days, and the midnight crossing survives.
    assert at(first["departs_at"]) == at(f"2026-10-08T23:30:00{TPE}")
    assert at(first["arrives_at"]) == at(f"2026-10-09T01:10:00{TPE}")
    assert at(second["departs_at"]) == at(f"2026-10-12T12:15:00{TPE}")  # still four days later


def test_the_shift_reads_the_taipei_day_not_the_utc_one(client):
    source = client.post("/api/trips", json={"name": "s"}).json()
    # 00:30 Taipei on 09-24 is 16:30 UTC on 09-23.
    client.post(f"/api/trips/{source['id']}/legs", json={
        "from_place": "a", "to_place": "b",
        "departs_at": f"2026-09-24T00:30:00{TPE}", "arrives_at": f"2026-09-24T02:00:00{TPE}"})
    new = copy(client, source, start_date="2026-10-05").json()
    assert at(new["legs"][0]["departs_at"]) == at(f"2026-10-05T00:30:00{TPE}")


def test_the_shift_can_go_backwards(client):
    source = make_source(client)
    new = copy(client, source, start_date="2026-09-01").json()
    assert at(new["legs"][0]["departs_at"]) == at(f"2026-09-01T23:30:00{TPE}")


def test_unlinked_from_names_exactly_the_legs_that_had_a_list(client):
    source = make_source(client)
    new = copy(client, source, start_date="2026-10-08").json()
    assert new["unlinked_from"] == [
        {"from_place": "台北車站", "to_place": "彰化火車站", "packing_list_name": "台北去彰化"}
    ]


def test_a_plain_create_has_an_empty_unlinked_from(client):
    assert client.post("/api/trips", json={"name": "x"}).json()["unlinked_from"] == []


def test_the_source_is_unchanged(client):
    source = make_source(client)
    copy(client, source, start_date="2026-10-08")
    assert client.get(f"/api/trips/{source['id']}").json() == source


def test_a_source_with_legs_and_no_start_date_is_a_422_and_writes_nothing(client):
    source = make_source(client)
    before = trip_count(client)
    response = copy(client, source)
    assert response.status_code == 422
    assert response.json()["detail"] == "start_date is required to copy a trip with legs."
    assert trip_count(client) == before


def test_an_unknown_source_is_a_404_and_writes_nothing(client):
    before = trip_count(client)
    response = client.post("/api/trips", json={"name": "x", "copy_from_id": 999999,
                                               "start_date": "2026-10-08"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Trip to copy from not found."
    assert trip_count(client) == before


def test_a_legless_source_needs_no_start_date(client):
    source = client.post("/api/trips", json={"name": "空", "notes": "n"}).json()
    response = copy(client, source)
    assert response.status_code == 201
    assert (response.json()["notes"], response.json()["legs"]) == ("n", [])


def test_a_start_date_without_a_source_is_ignored(client):
    response = client.post("/api/trips", json={"name": "x", "start_date": "2026-10-08"})
    assert response.status_code == 201


def test_the_requests_own_notes_win_over_the_sources(client):
    source = make_source(client)
    new = copy(client, source, start_date="2026-10-08", notes="我的").json()
    assert new["notes"] == "我的"


@pytest.mark.parametrize("bad", ["2026-13-01", "not a date"])
def test_a_malformed_start_date_is_a_422(client, bad):
    source = make_source(client)
    assert copy(client, source, start_date=bad).status_code == 422


def test_copying_as_a_template_keeps_the_dates_when_given_the_first_day(client):
    # 當作範本: the client sends the source's own first day as start_date.
    source = client.post("/api/trips", json={"name": "s"}).json()
    client.post(f"/api/trips/{source['id']}/legs", json={
        "from_place": "a", "to_place": "b",
        "departs_at": f"2026-09-24T18:06:00{TPE}", "arrives_at": f"2026-09-24T20:59:00{TPE}"})
    response = client.post("/api/trips", json={"name": "s（範本）", "kind": "template",
                                               "copy_from_id": source["id"],
                                               "start_date": "2026-09-24"})
    assert response.status_code == 201
    new = response.json()
    assert (new["kind"], new["usage"]) == ("template", None)
    assert at(new["legs"][0]["departs_at"]) == at(f"2026-09-24T18:06:00{TPE}")
    assert client.get(f"/api/trips/{source['id']}").json()["kind"] == "free"  # the source stays
