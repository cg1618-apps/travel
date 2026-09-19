"""Options are suggestions, not references, and every behaviour here follows
from that.

The item holds its category as text. So a rename has to rewrite the items, a
merge is what a name collision means, and a delete must leave the items alone —
three behaviours that would all be different if the item held a foreign key.
Each is asserted, because each looks like a bug from the other model's point of
view.
"""

import pytest

from app.models import LabelOption, PackingItem, PackingList


@pytest.fixture
def packing_list(db_session) -> PackingList:
    row = PackingList(name="Sapporo")
    db_session.add(row)
    db_session.commit()
    return row


def add_item(client, packing_list, **fields):
    return client.post(
        f"/api/packing-lists/{packing_list.id}/items",
        json={"name": "socks", **fields},
    )


def options(client, kind=None):
    query = f"?kind={kind}" if kind else ""
    return client.get(f"/api/label-options{query}").json()


# --------------------------------------------------------------------------
# Learning as you type
# --------------------------------------------------------------------------


def test_saving_an_item_records_its_category_as_an_option(client, packing_list):
    add_item(client, packing_list, category="clothes")
    assert [row["value"] for row in options(client, "category")] == ["clothes"]


def test_saving_an_item_records_its_bag_as_an_option(client, packing_list):
    add_item(client, packing_list, bag="carry-on")
    assert [row["value"] for row in options(client, "bag")] == ["carry-on"]


def test_the_same_value_is_not_recorded_twice(client, packing_list):
    # The unique constraint is on (kind, value); an upsert that did not check
    # first would raise on the second item using the same category, which is
    # the most ordinary thing a user can do.
    add_item(client, packing_list, name="socks", category="clothes")
    add_item(client, packing_list, name="shirt", category="clothes")
    assert len(options(client, "category")) == 1


def test_a_value_typed_into_a_patch_is_remembered_too(client, packing_list):
    item = add_item(client, packing_list).json()
    client.patch(f"/api/packing-items/{item['id']}", json={"category": "toiletries"})
    assert [row["value"] for row in options(client, "category")] == ["toiletries"]


def test_the_same_value_is_remembered_separately_for_each_kind(client, packing_list):
    # "day bag" is a plausible category and a plausible bag, and they are
    # different facts. The unique constraint is on the pair for this reason.
    add_item(client, packing_list, category="day bag", bag="day bag")
    assert [row["value"] for row in options(client, "category")] == ["day bag"]
    assert [row["value"] for row in options(client, "bag")] == ["day bag"]


def test_an_item_with_no_category_records_nothing(client, packing_list):
    add_item(client, packing_list)
    assert options(client, "category") == []


def test_options_are_listed_in_position_order(client, packing_list):
    add_item(client, packing_list, name="a", category="clothes")
    add_item(client, packing_list, name="b", category="documents")
    add_item(client, packing_list, name="c", category="electronics")
    assert [row["value"] for row in options(client, "category")] == [
        "clothes",
        "documents",
        "electronics",
    ]


def test_listing_without_a_kind_returns_both(client, packing_list):
    add_item(client, packing_list, category="clothes", bag="carry-on")
    assert len(options(client)) == 2


def test_an_unknown_kind_is_rejected(client):
    assert client.get("/api/label-options?kind=colour").status_code == 422


# --------------------------------------------------------------------------
# Tidying
# --------------------------------------------------------------------------


def test_an_option_reports_how_many_items_use_it(client, packing_list):
    add_item(client, packing_list, name="socks", category="clothes")
    add_item(client, packing_list, name="shirt", category="clothes")
    add_item(client, packing_list, name="passport", category="documents")

    by_value = {row["value"]: row["usage_count"] for row in options(client, "category")}
    # The rename screen says this before it rewrites anything, which is the
    # difference between a rename and a surprise.
    assert by_value == {"clothes": 2, "documents": 1}


def test_renaming_an_option_rewrites_the_items_that_used_it(
    client, db_session, packing_list
):
    add_item(client, packing_list, name="socks", category="cloths")
    option = options(client, "category")[0]

    response = client.patch(f"/api/label-options/{option['id']}", json={"value": "clothes"})
    assert response.status_code == 200

    # The item holds text, not a reference. A rename touching only the option
    # row would leave every existing item on the old value and the screen would
    # show both spellings.
    item = db_session.query(PackingItem).one()
    assert item.category == "clothes"


def test_renaming_a_bag_option_rewrites_the_bag_and_not_the_category(
    client, db_session, packing_list
):
    # The two kinds map to different columns, and getting that mapping wrong
    # would rewrite the wrong field while looking entirely successful.
    add_item(client, packing_list, category="clothes", bag="carry-on")
    bag_option = options(client, "bag")[0]

    client.patch(f"/api/label-options/{bag_option['id']}", json={"value": "cabin"})

    item = db_session.query(PackingItem).one()
    assert item.bag == "cabin"
    assert item.category == "clothes"


def test_renaming_onto_an_existing_option_merges(client, db_session, packing_list):
    add_item(client, packing_list, name="socks", category="cloths")
    add_item(client, packing_list, name="shirt", category="clothes")
    typo = next(row for row in options(client, "category") if row["value"] == "cloths")

    response = client.patch(f"/api/label-options/{typo['id']}", json={"value": "clothes"})
    assert response.status_code == 200

    # One option left, both items on it. The unique constraint would otherwise
    # have refused the rename outright, which is the unhelpful reading of a
    # collision that a rename is usually trying to fix.
    assert [row["value"] for row in options(client, "category")] == ["clothes"]
    assert db_session.query(LabelOption).count() == 1
    assert {item.category for item in db_session.query(PackingItem).all()} == {"clothes"}


def test_a_merge_reports_the_surviving_option(client, packing_list):
    add_item(client, packing_list, name="socks", category="cloths")
    add_item(client, packing_list, name="shirt", category="clothes")
    typo = next(row for row in options(client, "category") if row["value"] == "cloths")

    body = client.patch(f"/api/label-options/{typo['id']}", json={"value": "clothes"}).json()
    # The row the caller addressed no longer exists. Returning it, or 404ing,
    # would both be wrong: the rename succeeded.
    assert body["value"] == "clothes"
    assert body["usage_count"] == 2


def test_an_option_can_be_reordered(client, packing_list):
    add_item(client, packing_list, name="a", category="clothes")
    add_item(client, packing_list, name="b", category="documents")
    first = options(client, "category")[0]

    client.patch(f"/api/label-options/{first['id']}", json={"position": 99})
    assert [row["value"] for row in options(client, "category")] == [
        "documents",
        "clothes",
    ]


def test_renaming_to_the_same_value_changes_nothing(client, packing_list):
    add_item(client, packing_list, category="clothes")
    option = options(client, "category")[0]
    response = client.patch(
        f"/api/label-options/{option['id']}", json={"value": "clothes"}
    )
    assert response.status_code == 200
    assert [row["value"] for row in options(client, "category")] == ["clothes"]


# --------------------------------------------------------------------------
# Pruning
# --------------------------------------------------------------------------


def test_deleting_an_option_leaves_the_items_alone(client, db_session, packing_list):
    add_item(client, packing_list, category="clothes")
    option = options(client, "category")[0]

    assert client.delete(f"/api/label-options/{option['id']}").status_code == 204

    # Pruning a typo out of the suggestions must not blank the field on an item
    # legitimately using it. Deleting is about autocomplete and nothing else.
    assert db_session.query(PackingItem).one().category == "clothes"
    assert db_session.query(LabelOption).count() == 0


def test_a_deleted_option_comes_back_if_it_is_typed_again(client, packing_list):
    # It is learned from what gets typed, so it must be. Worth pinning: this is
    # surprising until you remember these are suggestions rather than records.
    add_item(client, packing_list, name="socks", category="clothes")
    option = options(client, "category")[0]
    client.delete(f"/api/label-options/{option['id']}")

    add_item(client, packing_list, name="shirt", category="clothes")
    assert [row["value"] for row in options(client, "category")] == ["clothes"]


def test_patching_an_option_that_does_not_exist_is_a_404(client):
    assert client.patch("/api/label-options/9999", json={"value": "x"}).status_code == 404


def test_deleting_an_option_that_does_not_exist_is_a_404(client):
    assert client.delete("/api/label-options/9999").status_code == 404
