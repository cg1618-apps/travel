"""筆記: notes with links, in groups that follow the packing-list group rule."""

import pytest

from app.models import NoteLink


def add(client, title="note", **fields):
    return client.post("/api/notes", json={"title": title, **fields})


def rows(client):
    """(title, group_name, position) in the order the notes page reads."""
    return [(n["title"], n["group_name"], n["position"]) for n in client.get("/api/notes").json()]


def titles(client):
    return [title for title, _, _ in rows(client)]


def put_order(client, note_ids):
    return client.put("/api/notes/order", json={"note_ids": note_ids})


@pytest.fixture
def three_groups(client):
    """台北 ×2, ungrouped ×1, 台中 ×1, in that order: positions 0..3.

    Load-bearing: a group with something AFTER it is what makes "the end of
    its group" differ from "the end of the list", and the refusals below need
    groups to split.
    """
    ids = {}
    for title, group in (("a", "台北"), ("b", "台北"), ("c", None), ("d", "台中")):
        ids[title] = add(client, title, group_name=group).json()["id"]
    assert rows(client) == [("a", "台北", 0), ("b", "台北", 1), ("c", None, 2), ("d", "台中", 3)]
    return ids


def test_a_note_reads_back_with_its_links_in_order(client):
    created = add(client, "訂房", description="第一行\n第二行",
                  links=["https://example.invalid/b", "https://example.invalid/a"])
    assert created.status_code == 201
    body = client.get("/api/notes").json()[0]
    assert body["links"] == ["https://example.invalid/b", "https://example.invalid/a"]
    assert body["description"] == "第一行\n第二行"
    assert body["group_name"] is None


@pytest.mark.parametrize("title", ["", "   "])
def test_a_note_needs_a_title(client, title):
    assert add(client, title).status_code == 422
    assert add(client, "x").status_code == 201  # mirror


def test_a_title_is_stripped_and_a_blank_group_is_no_group(client):
    body = add(client, "  訂房 ", group_name="  ").json()
    assert (body["title"], body["group_name"]) == ("訂房", None)


def test_a_blank_link_is_a_422(client):
    assert add(client, links=["https://example.invalid", " "]).status_code == 422


def test_a_new_note_joins_the_end_of_its_group(client, three_groups):
    assert add(client, "e", group_name="台北").json()["position"] == 2
    assert titles(client) == ["a", "b", "e", "c", "d"]


def test_a_new_ungrouped_note_joins_the_ungrouped_group(client, three_groups):
    add(client, "e")
    assert titles(client) == ["a", "b", "c", "e", "d"]


def test_a_new_group_goes_to_the_end(client, three_groups):
    add(client, "e", group_name="高雄")
    assert titles(client) == ["a", "b", "c", "d", "e"]


def test_changing_the_group_moves_the_note_to_the_end_of_it(client, three_groups):
    body = client.patch(f"/api/notes/{three_groups['d']}", json={"group_name": "台北"})
    assert body.status_code == 200
    assert titles(client) == ["a", "b", "d", "c"]


def test_a_patch_keeping_the_group_does_not_move_the_note(client, three_groups):
    client.patch(f"/api/notes/{three_groups['a']}", json={"group_name": "台北", "title": "A"})
    assert titles(client) == ["A", "b", "c", "d"]


def test_links_are_replaced_and_their_order_is_the_new_order(client, db_session):
    note = add(client, links=["https://example.invalid/1", "https://example.invalid/2"]).json()
    body = client.patch(f"/api/notes/{note['id']}",
                        json={"links": ["https://example.invalid/2", "https://example.invalid/1"]})
    assert body.json()["links"] == ["https://example.invalid/2", "https://example.invalid/1"]
    assert db_session.query(NoteLink).count() == 2


def test_a_patch_without_links_keeps_them(client):
    note = add(client, links=["https://example.invalid/1"]).json()
    body = client.patch(f"/api/notes/{note['id']}", json={"description": "x"}).json()
    assert body["links"] == ["https://example.invalid/1"]


@pytest.mark.parametrize("body", [{"title": None}, {"title": " "}, {"links": None}])
def test_a_patch_cannot_blank_the_title_or_null_the_links(client, body):
    note = add(client).json()
    assert client.patch(f"/api/notes/{note['id']}", json=body).status_code == 422
    assert client.patch(f"/api/notes/{note['id']}", json={"title": "y"}).status_code == 200


def test_deleting_a_note_takes_its_links(client, db_session):
    note = add(client, links=["https://example.invalid/1"]).json()
    assert client.delete(f"/api/notes/{note['id']}").status_code == 204
    assert db_session.query(NoteLink).count() == 0
    assert client.delete(f"/api/notes/{note['id']}").status_code == 404


def test_a_missing_note_is_a_404(client):
    assert client.patch("/api/notes/999999", json={"title": "x"}).status_code == 404


# --- ordering ---------------------------------------------------------------------


def test_an_order_moving_whole_groups_is_applied(client, three_groups):
    ids = three_groups
    response = put_order(client, [ids["d"], ids["b"], ids["a"], ids["c"]])
    assert response.status_code == 200
    assert [n["title"] for n in response.json()] == ["d", "b", "a", "c"]
    assert titles(client) == ["d", "b", "a", "c"]


def test_an_order_splitting_a_group_is_refused(client, three_groups):
    ids = three_groups
    refused = put_order(client, [ids["a"], ids["c"], ids["b"], ids["d"]])
    assert refused.status_code == 422
    assert refused.json()["detail"] == (
        'The order splits the "台北" group: a group\'s notes must be adjacent.')
    assert titles(client) == ["a", "b", "c", "d"]


def test_an_order_missing_a_note_is_refused(client, three_groups):
    ids = three_groups
    assert put_order(client, [ids["a"], ids["b"], ids["c"]]).status_code == 422
    assert titles(client) == ["a", "b", "c", "d"]


def test_an_order_naming_a_note_twice_is_refused(client, three_groups):
    ids = three_groups
    assert put_order(client, [ids["a"], ids["a"], ids["b"], ids["c"]]).status_code == 422


def test_an_empty_order_of_no_notes_is_accepted(client):
    assert put_order(client, []).json() == []
