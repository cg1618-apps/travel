"""Items: what the edge refuses, where a new one lands, and the two pieces of
state that deliberately do not talk to each other.

The count suggesting rather than setting the status, and the double-check
being independent of it, are both rules that read as over-engineering until
they are gone. They are asserted here so that simplifying either one breaks a
test rather than quietly changing what the app can express.
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


# --------------------------------------------------------------------------
# The edge
# --------------------------------------------------------------------------


def test_an_item_needs_a_name(client, packing_list):
    assert add_item(client, packing_list, name="").status_code == 422


def test_an_unknown_status_is_a_422_not_a_500(client, packing_list):
    # Rejected by the schema before the CHECK constraint ever sees it. Both
    # layers matter: the schema gives a usable message, the constraint is what
    # holds when something writes around the schema.
    assert add_item(client, packing_list, status="half").status_code == 422


def test_an_unknown_timing_is_a_422_not_a_500(client, packing_list):
    assert add_item(client, packing_list, timing="eventually").status_code == 422


def test_every_declared_status_and_timing_is_accepted(client, packing_list):
    # The mirror of the two refusals. A schema that rejected everything would
    # pass both of them and the application would be unusable.
    for status in ("not_packed", "packed", "no_need"):
        assert add_item(client, packing_list, status=status).status_code == 201
    for timing in ("whenever", "night_before", "day_of", "just_before"):
        assert add_item(client, packing_list, timing=timing).status_code == 201


def test_a_negative_count_is_refused(client, packing_list):
    assert add_item(client, packing_list, quantity=-1).status_code == 422
    assert add_item(client, packing_list, quantity_packed=-1).status_code == 422


def test_adding_an_item_to_a_list_that_does_not_exist_is_a_404(client):
    response = client.post("/api/packing-lists/9999/items", json={"name": "socks"})
    assert response.status_code == 404


# --------------------------------------------------------------------------
# Position
# --------------------------------------------------------------------------


def test_a_new_item_goes_to_the_end_of_its_list(client, packing_list):
    first = add_item(client, packing_list, name="first").json()
    second = add_item(client, packing_list, name="second").json()
    assert first["position"] == 0
    assert second["position"] == 1


def test_position_is_counted_per_list_not_globally(client, db_session, packing_list):
    other = PackingList(name="Hanoi")
    db_session.add(other)
    db_session.commit()

    add_item(client, packing_list, name="a")
    add_item(client, packing_list, name="b")
    first_on_the_other_list = client.post(
        f"/api/packing-lists/{other.id}/items", json={"name": "c"}
    ).json()

    # A global counter would put this at 2 and sort correctly by accident.
    assert first_on_the_other_list["position"] == 0


# --------------------------------------------------------------------------
# Quantity, status, and the deliberate gaps between them
# --------------------------------------------------------------------------


def test_packing_to_the_target_does_not_flip_the_status_by_itself(
    client, packing_list
):
    item = add_item(client, packing_list, quantity=3).json()
    updated = client.patch(
        f"/api/packing-items/{item['id']}", json={"quantity_packed": 3}
    ).json()
    # The count suggests; the client decides. A server that flipped this would
    # make "three of five is what I'm taking" impossible to say without
    # editing the target.
    assert updated["status"] == "not_packed"


def test_an_item_may_be_packed_while_short(client, packing_list):
    item = add_item(client, packing_list, quantity=5).json()
    updated = client.patch(
        f"/api/packing-items/{item['id']}",
        json={"quantity_packed": 3, "status": "packed"},
    ).json()
    assert updated["status"] == "packed"
    assert updated["quantity_packed"] == 3


def test_an_item_may_be_packed_beyond_its_target(client, packing_list):
    # Over-packing is not an error. Pinned so nobody adds a well-meaning
    # validation that makes the app refuse a real state.
    item = add_item(client, packing_list, quantity=2).json()
    response = client.patch(
        f"/api/packing-items/{item['id']}", json={"quantity_packed": 5}
    )
    assert response.status_code == 200
    assert response.json()["quantity_packed"] == 5


def test_a_quantity_may_be_left_out_entirely(client, packing_list):
    item = add_item(client, packing_list, name="hairbrush").json()
    assert item["quantity"] is None
    assert item["quantity_packed"] == 0


def test_double_checked_is_independent_of_status(client, packing_list):
    # Packed and still unverified is the state the second field exists for:
    # the passport is in the bag and nobody has looked at the expiry date.
    item = add_item(client, packing_list, name="passport", needs_double_check=True).json()
    updated = client.patch(
        f"/api/packing-items/{item['id']}", json={"status": "packed"}
    ).json()
    assert updated["status"] == "packed"
    assert updated["needs_double_check"] is True
    assert updated["double_checked"] is False


def test_double_checking_does_not_pack_the_item(client, packing_list):
    # And the mirror: the two fields do not drive each other in either
    # direction.
    item = add_item(client, packing_list, name="passport", needs_double_check=True).json()
    updated = client.patch(
        f"/api/packing-items/{item['id']}", json={"double_checked": True}
    ).json()
    assert updated["double_checked"] is True
    assert updated["status"] == "not_packed"


# --------------------------------------------------------------------------
# Updating and deleting
# --------------------------------------------------------------------------


def test_patching_changes_only_what_it_names(client, packing_list):
    item = add_item(client, packing_list, category="clothes", notes="warm").json()
    updated = client.patch(
        f"/api/packing-items/{item['id']}", json={"status": "packed"}
    ).json()
    assert updated["category"] == "clothes"
    assert updated["notes"] == "warm"


def test_a_field_can_be_cleared_by_sending_null(client, packing_list):
    # `exclude_unset` rather than `exclude_none` in the router: null is a real
    # value here - a category removed, a quantity that does not apply - and
    # excluding it would make these fields impossible to unset.
    item = add_item(client, packing_list, category="clothes", quantity=3).json()
    updated = client.patch(
        f"/api/packing-items/{item['id']}", json={"category": None, "quantity": None}
    ).json()
    assert updated["category"] is None
    assert updated["quantity"] is None


def test_patching_an_item_that_does_not_exist_is_a_404(client):
    assert client.patch("/api/packing-items/9999", json={"name": "x"}).status_code == 404


def test_deleting_an_item_leaves_its_list_alone(client, db_session, packing_list):
    item = add_item(client, packing_list).json()
    assert client.delete(f"/api/packing-items/{item['id']}").status_code == 204
    assert db_session.query(PackingItem).count() == 0
    assert db_session.query(PackingList).count() == 1


def test_deleting_an_item_that_does_not_exist_is_a_404(client):
    assert client.delete("/api/packing-items/9999").status_code == 404
