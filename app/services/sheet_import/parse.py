"""Read the owner's sheet export into plain dataclasses. Touches no database.

Columns are found by the text of the header row, never by position, so a
column the owner inserts does not shift the rest. Anything the parser cannot
place raises `ValueError` naming the tab, row and value - it never guesses.
Anything it can place but the owner should know about goes in `report`.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from app.constants import TAIPEI, DayType, Leg, Need, Status, Timing

PACKING_TABS = ("彰化回台北", "台北去彰化")
TRANSPORT_TAB = "Transportation"
THIS_TIME_TAB = "This time"

STATUS = {"未打包": Status.NOT_PACKED, "已打包": Status.PACKED, "不需打包": Status.NO_NEED}
DOUBLE_CHECK = {"不需確認": (False, False), "未確認": (True, False), "確認": (True, True)}
TIMINGS = {"隨時": Timing.WHENEVER, "出發前晚": Timing.NIGHT_BEFORE,
           "出發當天": Timing.DAY_OF, "出發前": Timing.JUST_BEFORE}
NEEDS = {"需要": Need.NEED, "需帶": Need.BRING, "需買": Need.BUY}
BOOKING = {"已訂票": "booked", "付款": "paid", "取票": "collected"}
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

#: (header prefix, day type, label in the owner's words); a bucket is the
#: column's name and its bounds in minutes, the same as `departures.js`.
DAY_COLUMNS = (("平日", DayType.WEEKDAY), ("假日", DayType.HOLIDAY))
BUCKETS = (("早", None, 12 * 60), ("中", 12 * 60, 14 * 60),
           ("下午", 14 * 60, 18 * 60), ("晚", 18 * 60, None))


@dataclass
class ParsedItem:
    category: str | None
    name: str
    detail: str | None
    quantity: int | None
    quantity_packed: int
    status: str
    needs_double_check: bool
    double_checked: bool
    timing: str
    need: str | None
    location: str | None
    notes: str | None


@dataclass
class ParsedList:
    name: str
    leg: str | None
    pair_id: str
    items: list[ParsedItem] = field(default_factory=list)


@dataclass
class ParsedDeparture:
    day_type: str
    time: time
    irregular: bool


@dataclass
class ParsedOption:
    mode: str
    advance_ticket: bool
    route_map_url: str | None
    timetable_url: str | None
    live_url: str | None
    direction: str | None
    line_from: str | None
    line_to: str | None
    board_at: str | None
    alight_at: str | None
    price: int | None
    duration: str | None
    headway: str | None
    notes: str | None = None
    departures: list[ParsedDeparture] = field(default_factory=list)


@dataclass
class ParsedRoute:
    from_place: str
    to_place: str
    notes: str | None = None
    options: list[ParsedOption] = field(default_factory=list)


@dataclass
class ParsedLeg:
    from_place: str
    to_place: str
    departs_at: datetime
    arrives_at: datetime
    service: str | None
    service_number: str | None
    seat: str | None
    price: int | None
    ticket_type: str | None
    booked: bool
    paid: bool
    collected: bool
    booking_code: str | None
    notes: str | None
    packing_list_name: str | None = None


@dataclass
class ParsedTrip:
    name: str
    legs: list[ParsedLeg]


@dataclass
class ParsedSheet:
    lists: list[ParsedList]
    routes: list[ParsedRoute]
    trip: ParsedTrip
    report: list[str]


def as_text(value) -> str | None:
    """Text for an identifier: 5158.0 is "5158", and blank is None."""
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    return text or None


def as_int(value) -> int | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return int(float(value))


def _header_index(row) -> dict[str, int]:
    return {str(cell).strip(): i for i, cell in enumerate(row) if cell is not None}


def _get(row, columns: dict[str, int], header: str):
    index = columns.get(header)
    return row[index] if index is not None and index < len(row) else None


def _text(row, columns, header) -> str | None:
    return as_text(_get(row, columns, header))


def _int(row, columns, header, where: str) -> int | None:
    """`as_int` on a cell, refusing a non-number by naming the tab, row and value."""
    cell = _get(row, columns, header)
    try:
        return as_int(cell)
    except ValueError as error:
        raise ValueError(f"{where}: cannot read {header} {cell!r}") from error


def _lookup(table: dict, value: str | None, default, where: str):
    """Map a sheet word to its stored value; blank is the default, unknown is refused."""
    if value is None:
        return default
    if value not in table:
        raise ValueError(f"{where}: unknown value {value!r}")
    return table[value]


def _is_blank(row) -> bool:
    return all(as_text(cell) is None for cell in row)


def _rows(ws):
    """(sheet row number, cells) for every row below the header."""
    for number, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not _is_blank(row):
            yield number, row


DEFAULTED = (("打包狀態", "未打包"), ("Double Check", "不需確認"), ("打包時機", "隨時"))


def _report_defaults(row, columns, where: str, name: str, report: list[str]) -> None:
    """Say which of the three vocabulary cells were blank and so took their default."""
    blank = [f"{header} became {default}" for header, default in DEFAULTED
             if _text(row, columns, header) is None]
    if blank:
        report.append(f"{where}: {name} left {', '.join(blank)}")


def _parse_packing(ws, report: list[str]) -> ParsedList:
    header = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
    columns = _header_index(header)
    detail_at = columns["項目"] + 1
    leg = Leg.OUTBOUND if "去" in ws.title else Leg.RETURN if "回" in ws.title else None
    parsed = ParsedList(ws.title, leg, "sheet-" + "-".join(sorted(PACKING_TABS)))
    category = name = None
    for number, row in _rows(ws):
        category = _text(row, columns, "類別") or category
        name = _text(row, columns, "項目") or name
        if name is None:
            raise ValueError(f"{ws.title} row {number}: no 項目 here or above")
        if name == "無":
            report.append(f"{ws.title} row {number}: 無 under {category} skipped")
            continue
        where = f"{ws.title} row {number}"
        _report_defaults(row, columns, where, name, report)
        check = _lookup(DOUBLE_CHECK, _text(row, columns, "Double Check"), (False, False), where)
        parsed.items.append(ParsedItem(
            category=category,
            name=name,
            detail=as_text(row[detail_at]) if detail_at < len(row) else None,
            quantity=_int(row, columns, "數量", where),
            quantity_packed=_int(row, columns, "已打包數量", where) or 0,
            status=_lookup(STATUS, _text(row, columns, "打包狀態"), Status.NOT_PACKED, where),
            needs_double_check=check[0],
            double_checked=check[1],
            timing=_lookup(TIMINGS, _text(row, columns, "打包時機"), Timing.WHENEVER, where),
            need=_lookup(NEEDS, _text(row, columns, "需求"), None, where),
            location=_text(row, columns, "取得地點"),
            notes=_text(row, columns, "備註"),
        ))
    return parsed


def _clock(minutes: int) -> time:
    minutes %= 24 * 60
    return time(minutes // 60, minutes % 60)


def _parse_time_token(token: str) -> tuple[time, bool]:
    irregular = token.startswith("*")
    hours, minutes = token.lstrip("*").strip().split(":")[:2]
    return time(int(hours), int(minutes)), irregular


def _parse_time_cell(value) -> list[tuple[time, bool]] | None:
    """The times in one schedule cell; None for `...`, the owner's "not known yet"."""
    if value is None:
        return []
    if isinstance(value, datetime):
        return [(value.time().replace(second=0, microsecond=0), False)]
    if isinstance(value, time):
        return [(value.replace(second=0, microsecond=0), False)]
    if isinstance(value, (int, float)):
        return [(_clock(round(value * 1440)), False)]
    text = str(value).strip()
    if text == "...":
        return None
    return [_parse_time_token(token.strip()) for token in text.split(",") if token.strip()]


def _bucket(t: time, bucket: str) -> str | None:
    """Why `t` does not belong in `bucket`'s column, or None when it does."""
    minutes = t.hour * 60 + t.minute
    _, low, high = next(b for b in BUCKETS if b[0] == bucket)
    if low is not None and minutes < low:
        return f"is before {low // 60}:00"
    if high is not None and minutes >= high:
        return f"is at or after {high // 60}:00"
    return None


def _parse_departures(row, columns, option: ParsedOption, where: str, report: list[str]) -> None:
    unknown: list[str] = []
    for prefix, day_type in DAY_COLUMNS:
        for bucket, _, _ in BUCKETS:
            cell = _get(row, columns, f"{prefix}班次 ({bucket})")
            try:
                times = _parse_time_cell(cell)
            except ValueError as error:
                raise ValueError(f"{where}: cannot read {prefix}班次 ({bucket}) {cell!r}") from error
            if times is None:
                unknown.append(f"{prefix} {bucket} 班次未知")
                continue
            for departure, irregular in times:
                if any(d.day_type == day_type and d.time == departure for d in option.departures):
                    report.append(f"{where}: {option.mode} {prefix} {bucket}: "
                                  f"{departure:%H:%M} is listed twice, kept once")
                    continue
                option.departures.append(ParsedDeparture(day_type, departure, irregular))
                problem = _bucket(departure, bucket)
                if problem:
                    report.append(f"{where}: {option.mode} {prefix} {bucket}: "
                                  f"{departure:%H:%M} {problem}")
    if unknown:
        option.notes = "; ".join(unknown)
        report.extend(f"{where}: {option.mode} {line}" for line in unknown)


def _parse_option(row, columns, where: str, report: list[str]) -> ParsedOption:
    option = ParsedOption(
        mode=_text(row, columns, "交通工具"),
        advance_ticket=_text(row, columns, "提前買票") == "需要",
        route_map_url=_text(row, columns, "路線圖"),
        timetable_url=_text(row, columns, "時刻表"),
        live_url=_text(row, columns, "即時動態"),
        direction=_text(row, columns, "方向"),
        line_from=_text(row, columns, "起點"),
        line_to=_text(row, columns, "終點"),
        board_at=_text(row, columns, "實際起點"),
        alight_at=_text(row, columns, "實際終點"),
        price=_int(row, columns, "價錢", where),
        duration=_text(row, columns, "時間"),
        headway=_text(row, columns, "班次間隔"),
    )
    _parse_departures(row, columns, option, where, report)
    return option


def _parse_transport(ws, report: list[str]) -> list[ParsedRoute]:
    columns = _header_index(next(ws.iter_rows(min_row=1, max_row=1, values_only=True)))
    routes: dict[tuple[str, str], ParsedRoute] = {}
    for number, row in _rows(ws):
        start, end = _text(row, columns, "目標起點"), _text(row, columns, "目標終點")
        where = f"{TRANSPORT_TAB} row {number}"
        if start is None or end is None:
            report.append(f"{where}: {start or end} has no {'destination' if end is None else 'start'}, skipped")
            continue
        route = routes.setdefault((start, end), ParsedRoute(start, end))
        if _text(row, columns, "交通工具"):
            route.options.append(_parse_option(row, columns, where, report))
        elif _text(row, columns, "時間"):
            route.notes = f"時間 {_text(row, columns, '時間')}"
    return list(routes.values())


_TIME_RANGE = re.compile(r"^(\w{3})\s+(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})$")


def _next_on_or_after(day: date, weekday: int) -> date:
    return day + timedelta(days=(weekday - day.weekday()) % 7)


def _leg_times(text: str | None, day: date | None, trip_start: date, where: str,
               report: list[str]):
    match = _TIME_RANGE.match(text or "")
    if not match or match.group(1) not in WEEKDAYS:
        raise ValueError(f"{where}: cannot read 時間 {text!r}")
    weekday = WEEKDAYS.index(match.group(1))
    if day is None and weekday != trip_start.weekday():
        raise ValueError(f"{where}: {match.group(1)} is not the weekday of {trip_start}")
    day = _next_on_or_after(day or trip_start, weekday)
    departs = datetime.combine(day, time(int(match.group(2)), int(match.group(3))), TAIPEI)
    arrives = datetime.combine(day, time(int(match.group(4)), int(match.group(5))), TAIPEI)
    if arrives == departs:
        raise ValueError(f"{where}: 時間 {text!r} arrives when it departs")
    if arrives < departs:
        arrives += timedelta(days=1)
        report.append(f"{where}: arrives before it departs, so it arrives the next day")
    return day, departs, arrives


def _booking_flags(text: str | None, where: str) -> dict[str, bool]:
    flags = {"booked": False, "paid": False, "collected": False}
    for word in (w.strip() for w in (text or "").split(",")):
        if word:
            flags[_lookup(BOOKING, word, None, f"{where} 訂票狀態")] = True
    return flags


def _link(leg: ParsedLeg, lists: list[ParsedList]) -> str | None:
    for candidate in lists:
        a, b = re.split("[去回]", candidate.name, maxsplit=1)
        if leg.from_place.startswith(a) and leg.to_place.startswith(b):
            return candidate.name
    return None


def _parse_this_time(ws, trip_start: date, trip_name: str, lists: list[ParsedList],
                     report: list[str]) -> ParsedTrip:
    columns = _header_index(next(ws.iter_rows(min_row=1, max_row=1, values_only=True)))
    legs: list[ParsedLeg] = []
    linked: set[str] = set()
    day = None
    for number, row in _rows(ws):
        where = f"{THIS_TIME_TAB} row {number}"
        day, departs, arrives = _leg_times(_text(row, columns, "時間"), day, trip_start, where, report)
        leg = ParsedLeg(
            from_place=_text(row, columns, "出發地點"), to_place=_text(row, columns, "目的地"),
            departs_at=departs, arrives_at=arrives,
            service=_text(row, columns, "車種"), service_number=_text(row, columns, "車號"),
            seat=_text(row, columns, "座位"), price=_int(row, columns, "價錢", where),
            ticket_type=_text(row, columns, "車票類型"),
            booking_code=_text(row, columns, "訂票代碼"), notes=_text(row, columns, "備註"),
            **_booking_flags(_text(row, columns, "訂票狀態"), where),
        )
        name = _link(leg, lists)
        if name is None:
            report.append(f"{where}: {leg.from_place} to {leg.to_place} has no packing list, left unlinked")
        elif name in linked:
            report.append(f"{where}: {name} is already linked to another leg, left unlinked")
        else:
            linked.add(name)
            leg.packing_list_name = name
        legs.append(leg)
    return ParsedTrip(trip_name, legs)


def parse_workbook(workbook, trip_start: date, trip_name: str) -> ParsedSheet:
    report: list[str] = []
    lists = [_parse_packing(workbook[tab], report) for tab in PACKING_TABS]
    routes = _parse_transport(workbook[TRANSPORT_TAB], report)
    trip = _parse_this_time(workbook[THIS_TIME_TAB], trip_start, trip_name, lists, report)
    return ParsedSheet(lists, routes, trip, report)
