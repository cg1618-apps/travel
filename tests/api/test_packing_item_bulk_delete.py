"""刪除所選: several items off one list, all or nothing."""

import pytest

from app.models import PackingList


@pytest.fixture
def packing_list(db_session) -> PackingList:
    row = PackingList(name="Sapporo")
    db_session.add(row)
    db_session.commit()
    return row


@pytest.fixture
def other_list(db_session) -> PackingList:
    row = PackingList(name="other")
    db_session.add(row)
    db_session.commit()
    return row


def add_item(client, packing_list, name):
    response = client.post(f"/api/packing-lists/{packing_list.id}/items", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def bulk_delete(client, packing_list, ids):
    return client.post(f"/api/packing-lists/{packing_list.id}/items/bulk-delete", json={"ids": ids})


def names(client, packing_list):
    body = client.get(f"/api/packing-lists/{packing_list.id}").json()
    return [row["name"] for row in body["items"]]


def test_it_removes_the_named_items_and_no_others(client, packing_list):
    ids = [add_item(client, packing_list, name) for name in ("a", "b", "c")]
    assert bulk_delete(client, packing_list, [ids[0], ids[2]]).status_code == 204
    assert names(client, packing_list) == ["b"]


def test_naming_another_lists_item_deletes_nothing(client, packing_list, other_list):
    mine = add_item(client, packing_list, "mine")
    foreign = add_item(client, other_list, "foreign")

    assert bulk_delete(client, packing_list, [mine, foreign]).status_code == 404

    assert names(client, packing_list) == ["mine"]
    assert names(client, other_list) == ["foreign"]
    # Mirror: the same item alone is accepted, so the foreign id did the refusing.
    assert bulk_delete(client, packing_list, [mine]).status_code == 204


def test_naming_a_missing_item_deletes_nothing(client, packing_list):
    mine = add_item(client, packing_list, "mine")
    assert bulk_delete(client, packing_list, [mine, 999999]).status_code == 404
    assert names(client, packing_list) == ["mine"]


def test_naming_an_item_twice_deletes_it_once(client, packing_list):
    mine = add_item(client, packing_list, "mine")
    assert bulk_delete(client, packing_list, [mine, mine]).status_code == 204
    assert names(client, packing_list) == []


def test_no_ids_changes_nothing(client, packing_list):
    add_item(client, packing_list, "mine")
    assert bulk_delete(client, packing_list, []).status_code == 204
    assert names(client, packing_list) == ["mine"]


def test_an_unknown_list_is_a_404(client):
    response = client.post("/api/packing-lists/999999/items/bulk-delete", json={"ids": []})
    assert response.status_code == 404
