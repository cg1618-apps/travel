from datetime import date, datetime, time

import pytest

from app.constants import TAIPEI
from app.services.sheet_import.parse import parse_workbook
from tests.sheet_fixture import workbook


@pytest.fixture
def sheet():
    return parse_workbook(workbook(), trip_start=date(2026, 9, 24), trip_name="彰化 ⇄ 台北")


def _list(sheet, name):
    return next(row for row in sheet.lists if row.name == name)


def _option(sheet, name):
    return next(o for r in sheet.routes for o in r.options if o.mode == name)


def test_blank_category_and_name_inherit_from_the_row_above(sheet):
    items = _list(sheet, "彰化回台北").items
    assert [(i.category, i.name, i.detail) for i in items] == [
        ("重要", "錢包", None), ("重要", "鑰匙", "家鑰匙"), ("重要", "鑰匙", "宿舍鑰匙"),
    ]


def test_the_sheet_vocabulary_maps_onto_stored_values(sheet):
    a, b, c = _list(sheet, "彰化回台北").items
    assert (a.status, a.needs_double_check, a.double_checked) == ("not_packed", True, False)
    assert (a.timing, a.need, a.location) == ("just_before", "bring", "彰化")
    assert (b.status, b.needs_double_check, b.double_checked) == ("packed", True, True)
    assert b.timing == "whenever"
    assert (c.status, c.needs_double_check, c.double_checked) == ("no_need", False, False)
    assert (c.timing, c.need, c.quantity, c.quantity_packed, c.notes) == (
        "night_before", None, 1, 0, "8/14沒帶")


def test_an_item_named_無_is_skipped_and_reported(sheet):
    assert all(i.name != "無" for p in sheet.lists for i in p.items)
    assert any("無" in line for line in sheet.report)


def test_lists_are_a_saved_round_trip_pair(sheet):
    back, there = _list(sheet, "彰化回台北"), _list(sheet, "台北去彰化")
    assert (back.leg, there.leg) == ("return", "outbound")
    assert back.saved and there.saved
    assert back.pair_id and back.pair_id == there.pair_id


def test_other_tabs_are_ignored(sheet):
    assert not any("Ignored" in line for line in sheet.report)


def test_routes_group_rows_by_their_two_places(sheet):
    assert [(r.from_place, r.to_place) for r in sheet.routes] == [
        ("彰化火車站", "宿舍"), ("宿舍", "彰化火車站"), ("彰化火車站", "台北車站"),
    ]
    first, second, third = sheet.routes
    assert [o.mode for o in first.options] == ["彰化客運6933A", "彰化客運6912"]
    assert second.options == []
    assert third.options == [] and third.notes == "時間 2h-2h30m"


def test_departures_read_strings_stars_times_and_day_fractions(sheet):
    option = _option(sheet, "彰化客運6933A")
    assert [(d.day_type, d.time, d.irregular) for d in option.departures] == [
        ("holiday", time(7, 30), False), ("holiday", time(9, 15), True),
        ("holiday", time(11, 35), False), ("holiday", time(14, 15), True),
        ("holiday", time(18, 40), False),
    ]


def test_a_time_in_the_wrong_column_is_imported_and_reported(sheet):
    assert any("11:35" in line for line in sheet.report)
    assert any(d.time == time(11, 35) for d in _option(sheet, "彰化客運6933A").departures)


def test_three_dots_means_unknown(sheet):
    option = _option(sheet, "彰化客運6912")
    assert option.departures == []
    assert "假日 早 班次未知" in option.notes and "假日 中 班次未知" in option.notes


def test_a_row_without_a_destination_is_skipped_and_reported(sheet):
    assert any("新烏日火車站" in line for line in sheet.report)


def test_option_fields_are_typed(sheet):
    o = _option(sheet, "彰化客運6933A")
    assert o.price == 22 and o.advance_ticket is False
    assert (o.board_at, o.alight_at, o.line_from) == ("彰化", "南瑤宮", "高鐵台中")
    assert (o.duration, o.route_map_url) == ("7m", "http://map")


def test_legs_get_dates_from_the_trip_start_in_taipei(sheet):
    first, second = sheet.trip.legs
    assert first.departs_at == datetime(2026, 9, 24, 18, 6, tzinfo=TAIPEI)
    assert first.arrives_at == datetime(2026, 9, 24, 20, 59, tzinfo=TAIPEI)
    assert second.departs_at == datetime(2026, 9, 28, 12, 15, tzinfo=TAIPEI)


def test_leg_identifiers_stay_text(sheet):
    leg = sheet.trip.legs[0]
    assert (leg.service_number, leg.booking_code, leg.price) == ("5158", "5891150", 550)


def test_booking_status_is_three_flags(sheet):
    first, second = sheet.trip.legs
    assert (first.booked, first.paid, first.collected) == (True, True, True)
    assert (second.booked, second.paid, second.collected) == (True, True, False)


def test_legs_link_to_the_list_for_their_journey(sheet):
    first, second = sheet.trip.legs
    assert first.packing_list_name == "彰化回台北"
    assert second.packing_list_name == "台北去彰化"


def test_a_trip_start_on_the_wrong_weekday_is_refused():
    with pytest.raises(ValueError):
        parse_workbook(workbook(), trip_start=date(2026, 9, 25), trip_name="x")


def test_an_unknown_status_is_refused_not_guessed():
    wb = workbook()
    wb["彰化回台北"]["F2"] = "半打包"
    with pytest.raises(ValueError, match="半打包"):
        parse_workbook(wb, trip_start=date(2026, 9, 24), trip_name="x")
