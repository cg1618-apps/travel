"""`on_dashboard` is `onDashboard` in kinds.js, written twice; these pin them together.

The cases are kinds.test.js's own. Change the rule in one place and not the
other, and one of the two suites goes red.
"""

from types import SimpleNamespace

from app.services.domain.dashboard import on_dashboard


def row(id, kind="free", usage=None):
    if usage is None and kind == "free":
        usage = "unused"
    return SimpleNamespace(id=id, kind=kind, usage=usage)


def test_keeps_in_use_and_upcoming_free_rows_in_use_first_order_otherwise_kept():
    rows = [row(1, "free", "upcoming"), row(2, "free", "unused"), row(3, "free", "in_use"),
            row(4, "free", "past"), row(5, "saved"), row(6, "free", "upcoming"),
            row(7, "free", "in_use")]
    assert [r.id for r in on_dashboard(rows)] == [3, 7, 1, 6]


def test_a_template_or_saved_row_is_never_current():
    assert on_dashboard([row(1, "template"), row(2, "saved")]) == []
