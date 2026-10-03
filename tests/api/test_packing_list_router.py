"""Creating a list, copying one, its kind and usage, and the refusal standing
between you and a list you did not mean to destroy.

`five_auto_saved` follows `test_auto_save.py`'s reasoning and is rebuilt here
for the same reason: every assertion about the queue refusing is vacuous
without it. A fresh database has nothing to drop, so the refusal cannot fail.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.constants import Kind, Usage
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
def five_auto_saved(db_session):
    """The queue at its limit, oldest first. Load-bearing: without it no
    refusal can fail."""
    rows = [
        make_list(
            db_session, f"L{day}", usage=Usage.PAST, auto_saved_at=EPOCH + timedelta(days=day)
        )
        for day in range(5)
    ]
    db_session.commit()
    return rows


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


def test_a_new_list_is_free_and_unused(client):
    body = client.post("/api/packing-lists", json={"name": "Osaka"}).json()
    assert (body["kind"], body["usage"], body["auto_saved_at"]) == ("free", "unused", None)
    assert (body["notes"], body["archive_note"]) == (None, None)


def test_a_template_can_be_created_blank_or_copied(client, db_session):
    source = make_list(db_session, "札幌", notes="冬天")
    db_session.add(PackingItem(list_id=source.id, name="傘", position=0))
    db_session.commit()
    blank = client.post("/api/packing-lists", json={"name": "空", "kind": "template"}).json()
    copy = client.post(
        "/api/packing-lists",
        json={"name": "札幌（範本）", "kind": "template", "copy_from_id": source.id},
    ).json()
    assert (blank["kind"], blank["usage"]) == ("template", None)
    assert (copy["kind"], copy["usage"]) == ("template", None)
    assert [item["name"] for item in copy["items"]] == ["傘"]
    db_session.expire_all()
    assert db_session.get(PackingList, source.id).kind == Kind.FREE  # the original stays


def test_a_list_cannot_be_created_saved(client):
    # Saving is a move, not a way to create. Mirror: `free` and `template`
    # are accepted above.
    assert client.post("/api/packing-lists", json={"name": "x", "kind": "saved"}).status_code == 422


def test_creating_is_never_refused_by_the_queue(five_auto_saved, client, db_session):
    assert client.post("/api/packing-lists", json={"name": "x"}).status_code == 201
    assert db_session.query(PackingList).count() == 6


# --------------------------------------------------------------------------
# Kind, usage and the 自動保存 queue
# --------------------------------------------------------------------------


def test_past_when_full_is_a_409_and_changes_nothing(five_auto_saved, client, db_session):
    target = make_list(db_session, "new", days=9)
    db_session.commit()
    refused = client.patch(f"/api/packing-lists/{target.id}", json={"usage": "past"})
    assert refused.status_code == 409
    # Naming it is the point: a 409 saying only "full" makes the caller guess
    # which list is about to go.
    assert "L0" in refused.json()["detail"]
    db_session.expire_all()
    assert db_session.get(PackingList, five_auto_saved[0].id) is not None
    assert db_session.get(PackingList, target.id).usage == Usage.UNUSED


def test_past_when_full_and_confirmed_drops_the_oldest(five_auto_saved, client, db_session):
    target = make_list(db_session, "new", days=9)
    oldest = five_auto_saved[0].id
    db_session.commit()
    response = client.patch(
        f"/api/packing-lists/{target.id}", json={"usage": "past", "evict_confirmed": True}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["usage"] == "past"
    assert body["auto_saved_at"] is not None
    db_session.expire_all()
    assert db_session.get(PackingList, oldest) is None


def test_past_with_room_needs_no_confirmation(five_auto_saved, client, db_session):
    # The mirror, on the same fixture: one slot free, nothing dropped.
    db_session.delete(five_auto_saved[-1])
    target = make_list(db_session, "new", days=9)
    db_session.commit()
    response = client.patch(f"/api/packing-lists/{target.id}", json={"usage": "past"})
    assert response.status_code == 200
    assert db_session.query(PackingList).count() == 5


def test_renaming_an_auto_saved_list_is_not_held_to_the_queue(
    five_auto_saved, client, db_session
):
    # It already occupies its slot. A check that counted it again would make
    # every edit of a full queue's lists fail.
    response = client.patch(
        f"/api/packing-lists/{five_auto_saved[0].id}", json={"name": "renamed"}
    )
    assert response.status_code == 200
    assert db_session.query(PackingList).count() == 5


def test_saving_and_unsaving(client, db_session):
    target = make_list(db_session, "x", usage=Usage.IN_USE)
    db_session.commit()
    url = f"/api/packing-lists/{target.id}"
    saved = client.patch(url, json={"kind": "saved"}).json()
    assert (saved["kind"], saved["usage"]) == ("saved", None)
    body = client.patch(url, json={"kind": "free"}).json()
    assert (body["kind"], body["usage"]) == ("free", "unused")


@pytest.mark.parametrize(
    "start,payload",
    [
        ({"kind": Kind.FREE}, {"kind": "template"}),
        ({"kind": Kind.TEMPLATE}, {"kind": "saved"}),
        ({"kind": Kind.TEMPLATE}, {"usage": "in_use"}),
        ({"kind": Kind.SAVED}, {"usage": "in_use"}),
    ],
)
def test_impossible_moves_are_a_422(client, db_session, start, payload):
    target = make_list(db_session, "x", **start)
    db_session.commit()
    assert client.patch(f"/api/packing-lists/{target.id}", json=payload).status_code == 422
    db_session.expire_all()
    assert db_session.get(PackingList, target.id).kind == start["kind"]


def test_notes_and_archive_note_are_editable(client, db_session):
    target = make_list(db_session, "x")
    db_session.commit()
    body = client.patch(
        f"/api/packing-lists/{target.id}", json={"notes": "帶傘", "archive_note": "下次少帶"}
    ).json()
    assert (body["notes"], body["archive_note"]) == ("帶傘", "下次少帶")


# --------------------------------------------------------------------------
# The index
# --------------------------------------------------------------------------


def test_the_index_has_four_shelves(client, db_session):
    make_list(db_session, "free", days=0)
    make_list(db_session, "auto", days=1, usage=Usage.PAST, auto_saved_at=EPOCH)
    make_list(db_session, "kept", days=2, kind=Kind.SAVED)
    make_list(db_session, "tpl", days=3, kind=Kind.TEMPLATE)
    db_session.commit()
    body = client.get("/api/packing-lists").json()
    shelves = {
        name: [row["name"] for row in body[name]]
        for name in ("free", "auto_saved", "saved", "templates")
    }
    assert shelves == {
        "free": ["free"],
        "auto_saved": ["auto"],
        "saved": ["kept"],
        "templates": ["tpl"],
    }
    assert body["evict_next"] == []


# One list of every kind/usage combination: each must be on exactly one shelf.
COMBINATIONS = [
    {"usage": Usage.IN_USE},
    {"usage": Usage.UPCOMING},
    {"usage": Usage.UNUSED},
    {"usage": Usage.PAST, "auto_saved_at": EPOCH},
    {"kind": Kind.SAVED},
    {"kind": Kind.TEMPLATE},
]
SHELVES = ("free", "auto_saved", "saved", "templates")


def test_every_list_is_on_exactly_one_shelf(client, db_session):
    """The regression for a row that sat in no section."""
    for number, fields in enumerate(COMBINATIONS):
        make_list(db_session, f"c{number}", days=number, **fields)
    db_session.commit()
    body = client.get("/api/packing-lists").json()
    shown = [row["name"] for shelf in SHELVES for row in body[shelf]]
    assert sorted(shown) == [f"c{number}" for number in range(len(COMBINATIONS))]


@pytest.mark.parametrize(
    "shelf,fields",
    [("free", {}), ("saved", {"kind": Kind.SAVED}), ("templates", {"kind": Kind.TEMPLATE})],
)
def test_shelves_are_newest_created_first(client, db_session, shelf, fields):
    # "tie" shares "newer"'s `created_at` and wins on the higher id.
    older = make_list(db_session, "older", days=0, **fields)
    make_list(db_session, "newer", days=1, **fields)
    make_list(db_session, "tie", days=1, **fields)
    db_session.commit()
    rows = client.get("/api/packing-lists").json()[shelf]
    assert [row["name"] for row in rows] == ["tie", "newer", "older"]
    assert datetime.fromisoformat(rows[-1]["created_at"]) == older.created_at


def test_auto_saved_is_newest_first(client, db_session):
    make_list(db_session, "older", days=5, usage=Usage.PAST, auto_saved_at=EPOCH)
    make_list(
        db_session, "newer", days=0, usage=Usage.PAST, auto_saved_at=EPOCH + timedelta(days=1)
    )
    db_session.commit()
    body = client.get("/api/packing-lists").json()
    assert [row["name"] for row in body["auto_saved"]] == ["newer", "older"]


def test_the_index_names_what_would_be_dropped_when_the_queue_is_full(five_auto_saved, client):
    # The dialog needs the id to offer 保存 instead; the 409's detail is a
    # plain string and cannot carry one. This is where it comes from.
    body = client.get("/api/packing-lists").json()
    assert [row["name"] for row in body["evict_next"]] == ["L0"]


# --------------------------------------------------------------------------
# Copying
# --------------------------------------------------------------------------


def test_a_copy_carries_the_definition_and_resets_the_state(client, db_session):
    source = make_list(db_session, "winter", kind=Kind.TEMPLATE)
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
    assert item["quantity_packed"] is None
    assert item["double_checked"] is False


def test_a_copy_carries_detail_need_and_location(client):
    source = client.post("/api/packing-lists", json={"name": "src"}).json()
    client.post(
        f"/api/packing-lists/{source['id']}/items",
        json={
            "name": "鑰匙",
            "detail": "家鑰匙",
            "need": "bring",
            "location": "彰化",
            "status": "packed",
        },
    )
    copy = client.post(
        "/api/packing-lists", json={"name": "copy", "copy_from_id": source["id"]}
    ).json()
    item = copy["items"][0]
    assert (item["detail"], item["need"], item["location"]) == ("家鑰匙", "bring", "彰化")
    assert item["status"] == "not_packed"


def test_a_copy_does_not_carry_the_source_list_s_own_fields(client, db_session):
    source = make_list(
        db_session,
        "winter",
        kind=Kind.TEMPLATE,
        departure_at=None,
        leg="outbound",
        notes="冬天",
        archive_note="太重",
    )
    db_session.commit()

    body = client.post(
        "/api/packing-lists", json={"name": "Sapporo", "copy_from_id": source.id}
    ).json()
    # A template copied as a template is a second template, which is how a
    # templates shelf fills up with trips; copied plainly it is 一般.
    assert (body["kind"], body["usage"]) == ("free", "unused")
    assert (body["notes"], body["archive_note"]) == (None, None)
    assert body["leg"] is None


def test_copying_from_a_list_that_does_not_exist_is_a_404(client):
    response = client.post(
        "/api/packing-lists", json={"name": "Sapporo", "copy_from_id": 9999}
    )
    assert response.status_code == 404


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


def test_a_list_can_be_renamed(client, db_session):
    packing_list = make_list(db_session, "Hanoi")
    db_session.commit()

    response = client.patch(f"/api/packing-lists/{packing_list.id}", json={"name": "Hue"})
    assert response.status_code == 200
    assert client.get(f"/api/packing-lists/{packing_list.id}").json()["name"] == "Hue"


def test_a_list_cannot_be_renamed_to_nothing(client, db_session):
    packing_list = make_list(db_session, "Hanoi")
    db_session.commit()

    for name in ("", None):
        response = client.patch(f"/api/packing-lists/{packing_list.id}", json={"name": name})
        assert response.status_code == 422
    assert client.get(f"/api/packing-lists/{packing_list.id}").json()["name"] == "Hanoi"


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


# --------------------------------------------------------------------------
# The index's per-list counts
# --------------------------------------------------------------------------


def test_the_index_counts_items_and_how_many_are_settled(client, db_session):
    # The index renders "3 / 11" per list. The counts come from the server
    # because the alternative is sending every item of every list so the client
    # can length them - a page-sized payload to render one fraction.
    packing_list = make_list(db_session, "Hanoi")
    db_session.add(PackingItem(list_id=packing_list.id, name="a", status="packed"))
    db_session.add(PackingItem(list_id=packing_list.id, name="b", status="no_need"))
    db_session.add(PackingItem(list_id=packing_list.id, name="c"))
    db_session.commit()

    row = client.get("/api/packing-lists").json()["free"][0]
    assert row["item_count"] == 3
    # `no_need` counts as settled: the question is what is left to deal with,
    # and a thing deliberately left behind has been dealt with.
    assert row["settled_count"] == 2


def test_an_empty_list_counts_zero_of_zero(client, db_session):
    make_list(db_session, "Hanoi")
    db_session.commit()
    row = client.get("/api/packing-lists").json()["free"][0]
    assert row["item_count"] == 0
    assert row["settled_count"] == 0


def test_the_counts_are_per_list_not_across_all_of_them(client, db_session):
    first = make_list(db_session, "Hanoi", days=0)
    second = make_list(db_session, "Seoul", days=1)
    db_session.add(PackingItem(list_id=first.id, name="a"))
    db_session.add(PackingItem(list_id=second.id, name="b"))
    db_session.add(PackingItem(list_id=second.id, name="c"))
    db_session.commit()

    by_name = {row["name"]: row for row in client.get("/api/packing-lists").json()["free"]}
    assert by_name["Hanoi"]["item_count"] == 1
    assert by_name["Seoul"]["item_count"] == 2


# --------------------------------------------------------------------------
# Reset
# --------------------------------------------------------------------------


def test_a_reset_unpacks_clears_counts_and_checks_but_leaves_no_need_alone(client):
    lst = client.post("/api/packing-lists", json={"name": "r"}).json()
    url = f"/api/packing-lists/{lst['id']}/items"
    client.post(url, json={"name": "packed", "status": "packed", "quantity": 2,
                           "quantity_packed": 2, "needs_double_check": True, "double_checked": True})
    # Load-bearing: without a no_need item the test cannot tell "left alone"
    # from "never there".
    client.post(url, json={"name": "skip", "status": "no_need"})
    other = client.post("/api/packing-lists", json={"name": "o"}).json()
    client.post(f"/api/packing-lists/{other['id']}/items", json={"name": "keep", "status": "packed"})

    response = client.post(f"/api/packing-lists/{lst['id']}/reset")
    assert response.status_code == 200
    by_name = {item["name"]: item for item in response.json()["items"]}
    assert by_name["packed"]["status"] == "not_packed"
    assert by_name["packed"]["quantity_packed"] is None
    assert by_name["packed"]["double_checked"] is False
    assert by_name["packed"]["needs_double_check"] is True  # definition, not state
    assert by_name["skip"]["status"] == "no_need"
    other_items = client.get(f"/api/packing-lists/{other['id']}").json()["items"]
    assert other_items[0]["status"] == "packed"


def test_resetting_a_missing_list_is_a_404(client):
    assert client.post("/api/packing-lists/999999/reset").status_code == 404


@pytest.mark.parametrize("field", ["kind", "usage"])
def test_a_null_for_a_required_list_field_is_a_422(client, field):
    lst = client.post("/api/packing-lists", json={"name": "彰化回台北"}).json()
    assert client.patch(f"/api/packing-lists/{lst['id']}", json={field: None}).status_code == 422
    # Mirror: the list's own date is nullable, and null clears it.
    cleared = client.patch(f"/api/packing-lists/{lst['id']}", json={"departure_at": None})
    assert cleared.status_code == 200
