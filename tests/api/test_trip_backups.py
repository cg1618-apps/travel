"""備案: an entry's backups, which are entries the trip does not count."""

from datetime import datetime

import pytest
from sqlalchemy import select

from app.models import TripLeg

TPE = "+08:00"
#: The default type, `other`, shows every label, so a backup of it has labels
#: left unticked. That is what makes the readiness tests below able to fail.
LEG = {"from_place": "台北", "to_place": "東京"}
TICKED = {"booked": True, "paid": True, "collected": True}


@pytest.fixture
def trip(client):
    return client.post("/api/trips", json={"name": "東京"}).json()


def add_entry(client, trip, **fields):
    response = client.post(f"/api/trips/{trip['id']}/legs", json={**LEG, **fields})
    assert response.status_code == 201
    return response.json()


def add_backup(client, entry, **fields):
    return client.post(
        f"/api/trip-legs/{entry['id']}/backups",
        json={"from_place": "松山", "to_place": "羽田", **fields},
    )


def read(client, trip):
    return client.get(f"/api/trips/{trip['id']}").json()


def test_a_backup_reads_back_under_its_entry_and_not_beside_it(client, trip):
    entry = add_entry(client, trip)
    backup = add_backup(client, entry, transport_type="flight", booking_code="XYZ789").json()
    assert (backup["backup_of_id"], backup["trip_id"]) == (entry["id"], trip["id"])

    body = read(client, trip)
    assert [leg["id"] for leg in body["legs"]] == [entry["id"]]
    assert [row["id"] for row in body["legs"][0]["backups"]] == [backup["id"]]
    assert body["legs"][0]["backups"][0]["booking_code"] == "XYZ789"


def test_an_entry_has_no_backups_until_one_is_added(client, trip):
    assert add_entry(client, trip)["backups"] == []


def test_backups_are_in_departure_order_undated_last(client, trip):
    entry = add_entry(client, trip)
    undated = add_backup(client, entry).json()
    late = add_backup(client, entry, departs_at=f"2026-12-01T13:00:00{TPE}").json()
    early = add_backup(client, entry, departs_at=f"2026-12-01T09:00:00{TPE}").json()
    order = [row["id"] for row in read(client, trip)["legs"][0]["backups"]]
    assert order == [early["id"], late["id"], undated["id"]]


def test_a_backup_has_the_same_refusals_as_an_entry(client, trip):
    entry = add_entry(client, trip)
    response = add_backup(
        client,
        entry,
        departs_at=f"2026-12-01T13:00:00{TPE}",
        arrives_at=f"2026-12-01T12:00:00{TPE}",
    )
    assert response.status_code == 422


def test_a_backup_of_a_missing_entry_is_a_404(client):
    assert add_backup(client, {"id": 0}).status_code == 404


def test_a_backup_cannot_have_backups(client, trip):
    entry = add_entry(client, trip)
    backup = add_backup(client, entry).json()
    assert add_backup(client, backup).status_code == 422
    # Mirror: the entry it hangs off can.
    assert add_backup(client, entry).status_code == 201


def test_a_backup_cannot_link_a_packing_list(client, trip):
    packing_list = client.post("/api/packing-lists", json={"name": "東京"}).json()
    entry = add_entry(client, trip)
    refused = add_backup(client, entry, packing_list_id=packing_list["id"])
    assert refused.status_code == 422

    backup = add_backup(client, entry).json()
    url = f"/api/trip-legs/{backup['id']}"
    assert client.patch(url, json={"packing_list_id": packing_list["id"]}).status_code == 422
    # Mirror: the same list links to the entry, so the refusal was about the backup.
    linked = client.patch(f"/api/trip-legs/{entry['id']}", json={"packing_list_id": packing_list["id"]})
    assert linked.status_code == 200


def test_a_backup_is_edited_through_the_entry_endpoint(client, trip):
    backup = add_backup(client, add_entry(client, trip)).json()
    body = client.patch(f"/api/trip-legs/{backup['id']}", json={"seat": "12A"}).json()
    assert body["seat"] == "12A"
    assert body["backup_of_id"] == backup["backup_of_id"]


# --- it counts for nothing the trip reads ---------------------------------------


@pytest.fixture
def ready_trip(client, trip):
    """Ready, with one entry fully ticked and marked done, so that anything a
    backup wrongly counted against it would show."""
    entry = add_entry(client, trip, **TICKED)
    url = f"/api/trips/{trip['id']}"
    body = client.patch(url, json={"ticket_status": "bought", "done": True}).json()
    assert (body["ready"], body["done"]) == (True, True)
    return {"trip": trip, "entry": entry}


def test_an_unticked_backup_does_not_stop_a_trip_being_ready(client, ready_trip):
    backup = add_backup(client, ready_trip["entry"]).json()
    assert backup["booked"] is False and backup["has_booked"] is True
    body = read(client, ready_trip["trip"])
    assert (body["ready"], body["done"]) == (True, True)
    # Mirror: the same unticked labels on an entry make it not ready.
    add_entry(client, ready_trip["trip"])
    body = read(client, ready_trip["trip"])
    assert (body["ready"], body["done"]) == (False, False)


def test_editing_a_backup_does_not_clear_done(client, ready_trip):
    backup = add_backup(client, ready_trip["entry"], **TICKED).json()
    client.patch(f"/api/trip-legs/{backup['id']}", json={"booked": False})
    assert read(client, ready_trip["trip"])["done"] is True
    # Mirror: the same edit on the entry does.
    client.patch(f"/api/trip-legs/{ready_trip['entry']['id']}", json={"booked": False})
    assert read(client, ready_trip["trip"])["done"] is False


def test_a_backup_does_not_block_going_one_way(client, trip):
    client.patch(f"/api/trips/{trip['id']}", json={"round_trip": True})
    entry = add_entry(client, trip)
    add_backup(client, entry)
    assert client.patch(f"/api/trips/{trip['id']}", json={"round_trip": False}).status_code == 200


def test_a_backup_stays_out_of_the_sections_and_follows_its_entry(client, trip):
    client.patch(f"/api/trips/{trip['id']}", json={"round_trip": True})
    entry = add_entry(client, trip, section="return")
    backup = add_backup(client, entry, section="return").json()
    assert backup["section"] is None

    moved = client.patch(f"/api/trip-legs/{backup['id']}", json={"section": "return"})
    assert moved.json()["section"] is None
    # Mirror: on the entry, the same write is what moves it.
    client.patch(f"/api/trip-legs/{entry['id']}", json={"section": "outbound"})
    body = read(client, trip)
    assert body["legs"][0]["section"] == "outbound"
    assert [row["id"] for row in body["legs"][0]["backups"]] == [backup["id"]]


# --- deleting -------------------------------------------------------------------


def test_deleting_a_backup_leaves_its_entry(client, trip):
    entry = add_entry(client, trip)
    backup = add_backup(client, entry).json()
    assert client.delete(f"/api/trip-legs/{backup['id']}").status_code == 204
    assert read(client, trip)["legs"][0]["id"] == entry["id"]
    assert read(client, trip)["legs"][0]["backups"] == []


def test_deleting_an_entry_takes_its_backups(client, db_session, trip):
    entry = add_entry(client, trip)
    add_backup(client, entry)
    assert client.delete(f"/api/trip-legs/{entry['id']}").status_code == 204
    db_session.expire_all()
    assert db_session.scalars(select(TripLeg)).all() == []


@pytest.mark.parametrize("bulk", [False, True])
def test_deleting_a_trip_takes_its_backups(client, db_session, trip, bulk):
    add_backup(client, add_entry(client, trip))
    if bulk:
        response = client.post("/api/trips/bulk-delete", json={"ids": [trip["id"]]})
    else:
        response = client.delete(f"/api/trips/{trip['id']}")
    assert response.status_code == 204
    db_session.expire_all()
    assert db_session.scalars(select(TripLeg)).all() == []


# --- copying --------------------------------------------------------------------


def test_a_copy_carries_backups_moved_with_their_state_reset(client, trip):
    entry = add_entry(client, trip, departs_at=f"2026-12-01T09:00:00{TPE}")
    add_backup(
        client,
        entry,
        departs_at=f"2026-12-01T13:00:00{TPE}",
        service_number="BR 192",
        seat="12A",
        booking_code="XYZ789",
        **TICKED,
    )
    copy = client.post(
        "/api/trips",
        json={"name": "再去", "copy_from_id": trip["id"], "start_date": "2027-01-10"},
    ).json()

    assert len(copy["legs"]) == 1
    new_entry = copy["legs"][0]
    [backup] = new_entry["backups"]
    assert backup["backup_of_id"] == new_entry["id"]
    assert backup["trip_id"] == copy["id"]
    assert datetime.fromisoformat(backup["departs_at"]) == datetime.fromisoformat(
        f"2027-01-10T13:00:00{TPE}"
    )
    assert backup["service_number"] == "BR 192"
    assert (backup["seat"], backup["booking_code"], backup["booked"]) == (None, None, False)
    # The source keeps its own.
    source = read(client, trip)["legs"][0]["backups"][0]
    assert source["booking_code"] == "XYZ789" and source["backup_of_id"] == entry["id"]


def test_a_backups_departure_does_not_decide_a_copys_start(client, trip):
    """The shift is anchored on the entries. A backup leaving a day earlier
    moves by the same days and does not become the trip's first day."""
    entry = add_entry(client, trip, departs_at=f"2026-12-02T09:00:00{TPE}")
    add_backup(client, entry, departs_at=f"2026-12-01T09:00:00{TPE}")
    copy = client.post(
        "/api/trips",
        json={"name": "再去", "copy_from_id": trip["id"], "start_date": "2027-01-10"},
    ).json()
    new_entry = copy["legs"][0]
    assert datetime.fromisoformat(new_entry["departs_at"]) == datetime.fromisoformat(
        f"2027-01-10T09:00:00{TPE}"
    )
    assert datetime.fromisoformat(new_entry["backups"][0]["departs_at"]) == datetime.fromisoformat(
        f"2027-01-09T09:00:00{TPE}"
    )
