"""設為主要: choosing which of an entry's options is the main one."""

import pytest

TPE = "+08:00"
LEG = {"from_place": "台北", "to_place": "東京"}
TICKED = {"booked": True, "paid": True, "collected": True}

#: Every field of an option, each different from `ENTRY`'s, so a field the swap
#: left behind shows up as a value that did not move.
OPTION = {
    "from_place": "松山",
    "to_place": "羽田",
    "departs_at": f"2026-10-02T09:00:00{TPE}",
    "arrives_at": f"2026-10-02T13:00:00{TPE}",
    "transport_type": "other",
    "direction": "北上",
    "service": "長榮",
    "service_number": "BR190",
    "seat": "12A",
    "price": 9000,
    "ticket_type": "經濟艙",
    "booked": True,
    "paid": True,
    "collected": False,
    "booking_code": "BACKUP1",
    "notes": "備案的備註",
    "has_collected": False,
}
ENTRY = {
    "departs_at": f"2026-10-01T08:00:00{TPE}",
    "arrives_at": f"2026-10-01T12:00:00{TPE}",
    "transport_type": "other",
    "direction": "南下",
    "service": "華航",
    "service_number": "CI100",
    "seat": "1A",
    "price": 100,
    "ticket_type": "商務艙",
    "booked": False,
    "paid": False,
    "collected": True,
    "booking_code": "ENTRY1",
    "notes": "原本的備註",
    "has_collected": True,
}
#: What belongs to the place in the trip, not to the option.
STAYS = {
    "id",
    "trip_id",
    "backup_of_id",
    "section",
    "packing_list_id",
    "packing_list_name",
    "backups",
}


@pytest.fixture
def trip(client):
    return client.post("/api/trips", json={"name": "東京"}).json()


def add_entry(client, trip, **fields):
    response = client.post(f"/api/trips/{trip['id']}/legs", json={**LEG, **fields})
    assert response.status_code == 201
    return response.json()


def add_backup(client, entry, **fields):
    response = client.post(
        f"/api/trip-legs/{entry['id']}/backups",
        json={"from_place": "松山", "to_place": "羽田", **fields},
    )
    assert response.status_code == 201
    return response.json()


def promote(client, leg):
    return client.post(f"/api/trip-legs/{leg['id']}/promote")


def read(client, trip):
    return client.get(f"/api/trips/{trip['id']}").json()


def option_of(row):
    return {field: value for field, value in row.items() if field not in STAYS}


@pytest.fixture
def ready_trip(client, trip):
    """Ready and marked done, so that a promotion making it not ready shows."""
    entry = add_entry(client, trip, **TICKED)
    url = f"/api/trips/{trip['id']}"
    body = client.patch(url, json={"ticket_status": "bought", "done": True}).json()
    assert (body["ready"], body["done"]) == (True, True)
    return {"trip": trip, "entry": entry}


def test_promoting_swaps_every_field_of_the_two_options(client, trip):
    entry = add_entry(client, trip, **ENTRY)
    backup = add_backup(client, entry, **OPTION)
    # Every field differs, or the assertions below could pass by standing still.
    differing = {f for f in option_of(entry) if entry[f] != backup[f]}
    assert differing >= set(OPTION) - {"transport_type"}

    response = promote(client, backup)

    assert response.status_code == 200
    [new_main] = read(client, trip)["legs"]
    [new_backup] = new_main["backups"]
    assert option_of(new_main) == option_of(backup)
    assert option_of(new_backup) == option_of(entry)
    assert response.json()["from_place"] == "松山"
    assert response.json()["backups"][0]["from_place"] == "台北"


def test_promoting_keeps_the_rows_ids_so_a_restore_still_inserts_in_order(client, trip):
    # A restore inserts by id and `backup_of_id` is an immediate foreign key, so
    # an entry must keep an id lower than its backups'.
    entry = add_entry(client, trip)
    backup = add_backup(client, entry)
    promote(client, backup)
    [main] = read(client, trip)["legs"]
    assert main["id"] == entry["id"]
    assert [row["id"] for row in main["backups"]] == [backup["id"]]
    assert main["backups"][0]["backup_of_id"] == entry["id"]


def test_promoting_leaves_the_other_backups_under_the_entry(client, trip):
    entry = add_entry(client, trip)
    chosen = add_backup(client, entry, from_place="選中")
    other = add_backup(client, entry, from_place="其他")
    promote(client, chosen)
    [main] = read(client, trip)["legs"]
    assert main["from_place"] == "選中"
    assert {row["id"]: row["from_place"] for row in main["backups"]} == {
        chosen["id"]: "台北",
        other["id"]: "其他",
    }


def test_promoting_twice_puts_the_first_option_back(client, trip):
    entry = add_entry(client, trip, **ENTRY)
    backup = add_backup(client, entry, **OPTION)
    promote(client, backup)
    promote(client, backup)
    [main] = read(client, trip)["legs"]
    assert option_of(main) == option_of(entry)
    assert option_of(main["backups"][0]) == option_of(backup)


def test_the_packing_list_and_the_section_stay_with_the_main_entry(client, trip):
    client.patch(f"/api/trips/{trip['id']}", json={"round_trip": True})
    packing_list = client.post("/api/packing-lists", json={"name": "去東京"}).json()
    entry = add_entry(
        client,
        trip,
        section="return",
        packing_list_id=packing_list["id"],
        departs_at=f"2026-10-01T08:00:00{TPE}",
    )
    backup = add_backup(client, entry, departs_at=f"2026-10-05T08:00:00{TPE}")

    assert promote(client, backup).status_code == 200

    [main] = read(client, trip)["legs"]
    assert (main["section"], main["packing_list_id"]) == ("return", packing_list["id"])
    assert (main["backups"][0]["section"], main["backups"][0]["packing_list_id"]) == (None, None)
    # The list is packed for the journey now planned, so its date follows.
    listed = client.get(f"/api/packing-lists/{packing_list['id']}").json()
    assert listed["departure_at"] == "2026-10-05"


def test_promoting_an_unticked_backup_clears_done(client, ready_trip):
    # Its unticked labels counted for nothing until it became the main one.
    backup = add_backup(client, ready_trip["entry"])
    assert read(client, ready_trip["trip"])["done"] is True
    promote(client, backup)
    body = read(client, ready_trip["trip"])
    assert (body["ready"], body["done"]) == (False, False)


def test_promoting_a_ticked_backup_leaves_done(client, ready_trip):
    # Mirror of the above: only the ticks differ, so the gate did the clearing.
    backup = add_backup(client, ready_trip["entry"], **TICKED)
    promote(client, backup)
    body = read(client, ready_trip["trip"])
    assert (body["ready"], body["done"]) == (True, True)


def test_an_entry_that_is_already_the_main_one_cannot_be_promoted(client, trip):
    entry = add_entry(client, trip)
    add_backup(client, entry)
    before = read(client, trip)
    response = promote(client, entry)
    assert response.status_code == 422
    assert response.json()["detail"] == "Only a backup can become the main entry."
    assert read(client, trip)["legs"] == before["legs"]


def test_promoting_a_missing_leg_is_a_404(client):
    assert client.post("/api/trip-legs/999999/promote").status_code == 404
