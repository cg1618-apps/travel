"""Groups on a list: where a new item lands, what a category change moves,
creating several at once, and the order a caller may set.

A group is the items sharing one `category`, null being a group of its own.
The sheet shows each group as one block, so every write that places an item
puts it inside its block, and a reorder that would split one is refused.
"""

import pytest

from app.models import PackingItem, PackingList


@pytest.fixture
def packing_list(db_session) -> PackingList:
    row = PackingList(name="Sapporo")
    db_session.add(row)
    db_session.commit()
    return row


def add_item(client, packing_list, **fields):
    payload = {"name": "socks", **fields}
    return client.post(f"/api/packing-lists/{packing_list.id}/items", json=payload)


def rows(client, packing_list):
    """(name, category, position) in the order the list reads."""
    items = client.get(f"/api/packing-lists/{packing_list.id}").json()["items"]
    return [(item["name"], item["category"], item["position"]) for item in items]


def names(client, packing_list):
    return [name for name, _, _ in rows(client, packing_list)]


@pytest.fixture
def three_groups(client, packing_list):
    """衣服 ×2, 重要 ×1, uncategorised ×1, in that order: positions 0..3.

    Load-bearing for most tests here: a group with something AFTER it is what
    makes "directly after the group" differ from "at the end of the list".
    """
    ids = {}
    for name, category in (("shirt", "衣服"), ("socks", "衣服"), ("passport", "重要"), ("misc", None)):
        ids[name] = add_item(client, packing_list, name=name, category=category).json()["id"]
    assert rows(client, packing_list) == [
        ("shirt", "衣服", 0), ("socks", "衣服", 1), ("passport", "重要", 2), ("misc", None, 3),
    ]
    return ids


# --------------------------------------------------------------------------
# Placement on create
# --------------------------------------------------------------------------


def test_a_new_item_joins_the_end_of_its_existing_group(client, packing_list, three_groups):
    item = add_item(client, packing_list, name="jacket", category="衣服").json()
    assert item["position"] == 2
    assert rows(client, packing_list) == [
        ("shirt", "衣服", 0), ("socks", "衣服", 1), ("jacket", "衣服", 2),
        ("passport", "重要", 3), ("misc", None, 4),
    ]


def test_a_new_item_of_a_new_category_goes_to_the_end(client, packing_list, three_groups):
    item = add_item(client, packing_list, name="pen", category="文具").json()
    assert item["position"] == 4
    assert names(client, packing_list) == ["shirt", "socks", "passport", "misc", "pen"]


def test_a_new_uncategorised_item_joins_the_uncategorised_group(client, packing_list):
    # Load-bearing: the null group is FIRST, with a categorised one after it,
    # so appending to the end would put this in the wrong block.
    add_item(client, packing_list, name="misc")
    add_item(client, packing_list, name="shirt", category="衣服")
    add_item(client, packing_list, name="other")
    assert names(client, packing_list) == ["misc", "other", "shirt"]


def test_after_id_still_places_exactly_where_it_is_told(client, packing_list, three_groups):
    # The group rule applies only when no after_id is sent.
    add_item(client, packing_list, name="key", category="衣服", after_id=three_groups["passport"])
    assert names(client, packing_list) == ["shirt", "socks", "passport", "key", "misc"]


def test_placement_does_not_shift_another_lists_items(client, db_session, packing_list, three_groups):
    other = PackingList(name="other")
    db_session.add(other)
    db_session.commit()
    for name in ("x", "y", "z"):
        add_item(client, other, name=name, category="衣服")
    add_item(client, packing_list, name="jacket", category="衣服")
    assert rows(client, other) == [("x", "衣服", 0), ("y", "衣服", 1), ("z", "衣服", 2)]


# --------------------------------------------------------------------------
# Changing an item's category
# --------------------------------------------------------------------------


def test_changing_category_moves_the_item_to_the_end_of_its_new_group(
    client, packing_list, three_groups
):
    response = client.patch(
        f"/api/packing-items/{three_groups['misc']}", json={"category": "衣服"}
    )
    assert response.status_code == 200
    assert names(client, packing_list) == ["shirt", "socks", "misc", "passport"]


def test_changing_category_to_a_new_one_moves_the_item_to_the_end(
    client, packing_list, three_groups
):
    client.patch(f"/api/packing-items/{three_groups['shirt']}", json={"category": "文具"})
    assert names(client, packing_list) == ["socks", "passport", "misc", "shirt"]


def test_clearing_category_moves_the_item_into_the_uncategorised_group(
    client, packing_list, three_groups
):
    add_item(client, packing_list, name="pen", category="文具")
    client.patch(f"/api/packing-items/{three_groups['shirt']}", json={"category": None})
    assert names(client, packing_list) == ["socks", "passport", "misc", "shirt", "pen"]


def test_a_patch_that_keeps_the_category_does_not_move_the_item(
    client, packing_list, three_groups
):
    # Mirror of the moves above: the same category, sent explicitly, and a
    # PATCH that does not name category at all, both leave it where it was.
    client.patch(f"/api/packing-items/{three_groups['shirt']}", json={"category": "衣服"})
    client.patch(f"/api/packing-items/{three_groups['shirt']}", json={"notes": "warm"})
    assert names(client, packing_list) == ["shirt", "socks", "passport", "misc"]


def test_a_position_sent_with_the_category_wins_over_the_move(client, packing_list, three_groups):
    # Load-bearing pairing: without the position, this PATCH would move misc
    # to 2 (after socks); with it, misc goes where it was told.
    response = client.patch(
        f"/api/packing-items/{three_groups['misc']}", json={"category": "衣服", "position": 7}
    )
    assert response.json()["position"] == 7


# --------------------------------------------------------------------------
# Bulk create
# --------------------------------------------------------------------------


def bulk(client, packing_list, items):
    return client.post(
        f"/api/packing-lists/{packing_list.id}/items/bulk-create", json={"items": items}
    )


def test_bulk_create_places_each_item_by_its_group_in_request_order(
    client, packing_list, three_groups
):
    response = bulk(client, packing_list, [
        {"name": "pen", "category": "文具"},
        {"name": "jacket", "category": "衣服"},
        {"name": "ruler", "category": "文具"},
        {"name": "visa", "category": "重要"},
    ])
    assert response.status_code == 201
    assert [item["name"] for item in response.json()] == ["pen", "jacket", "ruler", "visa"]
    # Two new items of one new category end up adjacent, in the order sent.
    assert names(client, packing_list) == [
        "shirt", "socks", "jacket", "passport", "visa", "misc", "pen", "ruler",
    ]
    assert [position for _, _, position in rows(client, packing_list)] == list(range(8))


def test_bulk_create_remembers_labels(client, packing_list):
    bulk(client, packing_list, [{"name": "pen", "category": "文具", "bag": "背包"}])
    categories = [row["value"] for row in client.get("/api/label-options?kind=category").json()]
    assert categories == ["文具"]


def test_one_bad_item_creates_nothing(client, packing_list, three_groups):
    # Load-bearing: the bad item is LAST, so a non-atomic create would already
    # have written the first one when it reached it.
    response = bulk(client, packing_list, [
        {"name": "pen", "category": "文具"},
        {"name": "", "category": "文具"},
    ])
    assert response.status_code == 422
    assert names(client, packing_list) == ["shirt", "socks", "passport", "misc"]
    # Mirror: the same body without the bad item is accepted.
    assert bulk(client, packing_list, [{"name": "pen", "category": "文具"}]).status_code == 201


def test_bulk_create_needs_at_least_one_item(client, packing_list):
    assert bulk(client, packing_list, []).status_code == 422


def test_bulk_create_on_an_unknown_list_is_a_404(client):
    response = client.post(
        "/api/packing-lists/999999/items/bulk-create", json={"items": [{"name": "x"}]}
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------
# Reorder
# --------------------------------------------------------------------------


def reorder(client, packing_list, item_ids):
    return client.put(f"/api/packing-lists/{packing_list.id}/order", json={"item_ids": item_ids})


def test_reorder_sets_positions_and_returns_the_list(client, packing_list, three_groups):
    ids = three_groups
    order = [ids["misc"], ids["passport"], ids["socks"], ids["shirt"]]
    response = reorder(client, packing_list, order)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == packing_list.id
    assert [item["id"] for item in body["items"]] == order
    assert [item["position"] for item in body["items"]] == [0, 1, 2, 3]
    assert names(client, packing_list) == ["misc", "passport", "socks", "shirt"]


UNTOUCHED = ["shirt", "socks", "passport", "misc"]


def test_reorder_missing_an_item_is_refused(client, packing_list, three_groups):
    ids = three_groups
    response = reorder(client, packing_list, [ids["shirt"], ids["socks"], ids["passport"]])
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert names(client, packing_list) == UNTOUCHED


def test_reorder_naming_another_lists_item_is_refused(client, db_session, packing_list, three_groups):
    other = PackingList(name="other")
    db_session.add(other)
    db_session.commit()
    foreign = add_item(client, other, name="far").json()["id"]
    ids = three_groups
    response = reorder(
        client, packing_list, [ids["misc"], ids["passport"], ids["socks"], ids["shirt"], foreign]
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert names(client, packing_list) == UNTOUCHED
    assert names(client, other) == ["far"]


def test_reorder_naming_an_item_twice_is_refused(client, packing_list, three_groups):
    ids = three_groups
    # Same length as the list, so only the duplicate check can refuse it.
    response = reorder(client, packing_list, [ids["misc"], ids["misc"], ids["passport"], ids["socks"]])
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert names(client, packing_list) == UNTOUCHED


def test_reorder_that_splits_a_group_is_refused(client, packing_list, three_groups):
    ids = three_groups
    response = reorder(client, packing_list, [ids["shirt"], ids["passport"], ids["socks"], ids["misc"]])
    assert response.status_code == 422
    assert "衣服" in response.json()["detail"]
    assert names(client, packing_list) == UNTOUCHED


def test_reorder_that_splits_the_uncategorised_group_is_refused(client, packing_list, three_groups):
    ids = three_groups
    extra = add_item(client, packing_list, name="extra").json()["id"]
    response = reorder(
        client, packing_list, [extra, ids["shirt"], ids["socks"], ids["passport"], ids["misc"]]
    )
    assert response.status_code == 422
    # Mirror: the uncategorised items adjacent is accepted.
    response = reorder(
        client, packing_list, [extra, ids["misc"], ids["shirt"], ids["socks"], ids["passport"]]
    )
    assert response.status_code == 200


def test_reorder_on_an_unknown_list_is_a_404(client):
    assert client.put("/api/packing-lists/999999/order", json={"item_ids": []}).status_code == 404


def test_reorder_of_an_empty_list_with_no_ids_is_accepted(client, packing_list):
    assert reorder(client, packing_list, []).status_code == 200


def test_positions_after_reorder_are_what_the_database_holds(client, db_session, packing_list, three_groups):
    ids = three_groups
    reorder(client, packing_list, [ids["passport"], ids["shirt"], ids["socks"], ids["misc"]])
    db_session.expire_all()
    stored = {item.name: item.position for item in db_session.query(PackingItem).all()}
    assert stored == {"passport": 0, "shirt": 1, "socks": 2, "misc": 3}
