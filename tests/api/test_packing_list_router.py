"""Creating a list, copying one, and the refusal standing between you and a
list you did not mean to destroy.

`three_working_lists` comes from `test_slots.py`'s reasoning and is rebuilt
here for the same reason: every assertion about the cap refusing is vacuous
without it. A fresh database has nothing to evict, so the refusal cannot fail.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models import PackingItem, PackingList

EPOCH = datetime(2026, 9, 1, tzinfo=timezone.utc)


def make_list(db_session, name, *, days=0, **overrides) -> PackingList:
    packing_list = PackingList(
        name=name, created_at=EPOCH + timedelta(days=days), **overrides
    )
    db_session.add(packing_list)
    db_session.flush()
    return packing_list


@pytest.fixture
def three_working_lists(db_session):
    """Three working lists, oldest first. Load-bearing, not scene setting."""
    lists = [
        make_list(db_session, "Kyoto", days=0),
        make_list(db_session, "Seoul", days=1),
        make_list(db_session, "Taipei", days=2),
    ]
    db_session.commit()
    return lists


# --------------------------------------------------------------------------
# Creating
# --------------------------------------------------------------------------


def test_a_list_can_be_created_with_nothing_but_a_name(client):
    response = client.post("/api/packing-lists", json={"name": "Hanoi"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Hanoi"
    # A list needs no trip and no date. That is the whole reason departure_at
    # is nullable, so it is asserted rather than assumed.
    assert body["departure_at"] is None
    assert body["items"] == []


def test_a_name_is_required(client):
    assert client.post("/api/packing-lists", json={"name": ""}).status_code == 422
    assert client.post("/api/packing-lists", json={}).status_code == 422


# --------------------------------------------------------------------------
# The cap
# --------------------------------------------------------------------------


def test_creating_a_fourth_list_refuses_and_names_what_would_be_destroyed(
    three_working_lists, client
):
    response = client.post("/api/packing-lists", json={"name": "Osaka"})
    assert response.status_code == 409
    # Naming it is the point. A 409 saying only "cap reached" makes the caller
    # guess which list is about to go, and the caller would guess wrong.
    assert "Kyoto" in response.json()["detail"]


def test_nothing_is_created_or_destroyed_by_a_refused_create(
    three_working_lists, client, db_session
):
    client.post("/api/packing-lists", json={"name": "Osaka"})
    names = sorted(row.name for row in db_session.query(PackingList).all())
    assert names == ["Kyoto", "Seoul", "Taipei"]


def test_confirming_creates_the_list_and_deletes_the_oldest(
    three_working_lists, client, db_session
):
    response = client.post(
        "/api/packing-lists", json={"name": "Osaka", "evict_confirmed": True}
    )
    assert response.status_code == 201
    names = sorted(row.name for row in db_session.query(PackingList).all())
    assert names == ["Osaka", "Seoul", "Taipei"]


def test_a_third_list_needs_no_confirmation(three_working_lists, client, db_session):
    # The mirror, on the same fixture: with room to spare the create succeeds
    # unconfirmed and destroys nothing. Without this, a cap that refused
    # everything would pass every test above.
    db_session.delete(three_working_lists[-1])
    db_session.commit()

    response = client.post("/api/packing-lists", json={"name": "Osaka"})
    assert response.status_code == 201
    names = sorted(row.name for row in db_session.query(PackingList).all())
    assert names == ["Kyoto", "Osaka", "Seoul"]


def test_a_saved_list_can_be_created_past_the_cap(three_working_lists, client):
    # Saved lists are exempt, so creating one is never a reason to destroy
    # anything.
    response = client.post(
        "/api/packing-lists", json={"name": "kept", "saved": True}
    )
    assert response.status_code == 201


def test_a_template_can_be_created_past_the_cap(three_working_lists, client):
    response = client.post(
        "/api/packing-lists", json={"name": "winter", "template": True}
    )
    assert response.status_code == 201


def test_un_saving_a_list_is_held_to_the_cap(three_working_lists, client, db_session):
    # Otherwise the cap is enforceable only at creation, and save-then-unsave
    # is a way to hold five working lists with nothing complaining.
    kept = make_list(db_session, "kept", days=9, saved=True)
    db_session.commit()

    response = client.patch(f"/api/packing-lists/{kept.id}", json={"saved": False})
    assert response.status_code == 409
    assert "Kyoto" in response.json()["detail"]


def test_un_saving_with_confirmation_evicts(three_working_lists, client, db_session):
    kept = make_list(db_session, "kept", days=9, saved=True)
    db_session.commit()

    response = client.patch(
        f"/api/packing-lists/{kept.id}", json={"saved": False, "evict_confirmed": True}
    )
    assert response.status_code == 200
    names = sorted(row.name for row in db_session.query(PackingList).all())
    assert names == ["Seoul", "Taipei", "kept"]


def test_renaming_a_working_list_is_not_held_to_the_cap(
    three_working_lists, client, db_session
):
    # It already occupies its slot. A cap check that counted it again would
    # make every rename of a third list fail.
    response = client.patch(
        f"/api/packing-lists/{three_working_lists[0].id}", json={"name": "Kyōto"}
    )
    assert response.status_code == 200
    assert db_session.query(PackingList).count() == 3


# --------------------------------------------------------------------------
# The index
# --------------------------------------------------------------------------


def test_the_index_sorts_lists_onto_three_shelves(client, db_session):
    make_list(db_session, "working", days=0)
    make_list(db_session, "kept", days=1, saved=True)
    make_list(db_session, "winter", days=2, template=True)
    db_session.commit()

    body = client.get("/api/packing-lists").json()
    assert [row["name"] for row in body["recent"]] == ["working"]
    assert [row["name"] for row in body["saved"]] == ["kept"]
    assert [row["name"] for row in body["templates"]] == ["winter"]


def test_a_list_that_is_both_saved_and_a_template_appears_on_both_shelves(
    client, db_session
):
    make_list(db_session, "both", days=0, saved=True, template=True)
    db_session.commit()

    body = client.get("/api/packing-lists").json()
    assert [row["name"] for row in body["saved"]] == ["both"]
    assert [row["name"] for row in body["templates"]] == ["both"]
    assert body["recent"] == []


def test_the_index_names_what_would_be_evicted_when_the_cap_is_full(
    three_working_lists, client
):
    # The dialog needs the id to offer "save it instead"; the 409's detail is a
    # plain string and cannot carry one. This is where it comes from.
    body = client.get("/api/packing-lists").json()
    assert [row["name"] for row in body["evict_next"]] == ["Kyoto"]


def test_the_index_offers_nothing_to_evict_when_there_is_room(client, db_session):
    make_list(db_session, "alone", days=0)
    db_session.commit()
    assert client.get("/api/packing-lists").json()["evict_next"] == []


# --------------------------------------------------------------------------
# Copying
# --------------------------------------------------------------------------


def test_a_copy_carries_the_definition_and_resets_the_state(client, db_session):
    source = make_list(db_session, "winter", template=True)
    db_session.add(
        PackingItem(
            list_id=source.id,
            name="socks",
            category="clothes",
            bag="checked",
            quantity=5,
            unit="pairs",
            timing="night_before",
            needs_double_check=True,
            notes="the warm ones",
            status="packed",
            quantity_packed=5,
            double_checked=True,
        )
    )
    db_session.commit()

    response = client.post(
        "/api/packing-lists", json={"name": "Sapporo", "copy_from_id": source.id}
    )
    assert response.status_code == 201

    item = response.json()["items"][0]
    assert item["name"] == "socks"
    assert item["category"] == "clothes"
    assert item["bag"] == "checked"
    assert item["quantity"] == 5
    assert item["unit"] == "pairs"
    assert item["timing"] == "night_before"
    assert item["needs_double_check"] is True
    assert item["notes"] == "the warm ones"

    assert item["status"] == "not_packed"
    assert item["quantity_packed"] == 0
    assert item["double_checked"] is False


def test_a_copy_does_not_carry_the_source_list_s_own_fields(client, db_session):
    source = make_list(
        db_session, "winter", template=True, departure_at=None, leg="outbound"
    )
    db_session.commit()

    body = client.post(
        "/api/packing-lists", json={"name": "Sapporo", "copy_from_id": source.id}
    ).json()
    # A template copied with template=True is a second template, which is how
    # a templates shelf fills up with trips.
    assert body["template"] is False
    assert body["saved"] is False
    assert body["leg"] is None


def test_copying_from_a_list_that_does_not_exist_is_a_404(client):
    response = client.post(
        "/api/packing-lists", json={"name": "Sapporo", "copy_from_id": 9999}
    )
    assert response.status_code == 404


def test_a_failed_copy_does_not_cost_you_the_oldest_list(
    three_working_lists, client, db_session
):
    # The source is resolved before the cap is enforced. The other order would
    # evict a real list and then fail the request, which is the worst possible
    # combination.
    client.post(
        "/api/packing-lists",
        json={"name": "Sapporo", "copy_from_id": 9999, "evict_confirmed": True},
    )
    names = sorted(row.name for row in db_session.query(PackingList).all())
    assert names == ["Kyoto", "Seoul", "Taipei"]


# --------------------------------------------------------------------------
# Reading, updating, deleting
# --------------------------------------------------------------------------


def test_reading_a_list_returns_its_items_in_position_order(client, db_session):
    packing_list = make_list(db_session, "Hanoi")
    db_session.add(PackingItem(list_id=packing_list.id, name="second", position=2))
    db_session.add(PackingItem(list_id=packing_list.id, name="first", position=1))
    db_session.commit()

    body = client.get(f"/api/packing-lists/{packing_list.id}").json()
    assert [item["name"] for item in body["items"]] == ["first", "second"]


def test_reading_a_list_that_does_not_exist_is_a_404(client):
    assert client.get("/api/packing-lists/9999").status_code == 404


def test_patching_changes_only_what_it_names(client, db_session):
    packing_list = make_list(db_session, "Hanoi", departure_at=None)
    db_session.commit()

    body = client.patch(
        f"/api/packing-lists/{packing_list.id}", json={"departure_at": "2026-10-01"}
    ).json()
    assert body["departure_at"] == "2026-10-01"
    assert body["name"] == "Hanoi"


def test_an_unknown_leg_is_rejected_at_the_edge(client, db_session):
    packing_list = make_list(db_session, "Hanoi")
    db_session.commit()
    response = client.patch(
        f"/api/packing-lists/{packing_list.id}", json={"leg": "sideways"}
    )
    assert response.status_code == 422


def test_deleting_a_list_takes_its_items_with_it(client, db_session):
    packing_list = make_list(db_session, "Hanoi")
    db_session.add(PackingItem(list_id=packing_list.id, name="passport"))
    db_session.commit()

    assert client.delete(f"/api/packing-lists/{packing_list.id}").status_code == 204
    assert db_session.query(PackingList).count() == 0
    assert db_session.query(PackingItem).count() == 0


def test_deleting_a_list_that_does_not_exist_is_a_404(client):
    assert client.delete("/api/packing-lists/9999").status_code == 404
