"""The readable tabs: what the sheet shows a person when the app is down.

Output only - the restore never reads them. They use the owner's own words,
the ones `frontend/src/lib/labels.js` shows on screen and the importer reads,
mirrored below as constants; times are Asia/Taipei. Each builder returns a
matrix of cells, and nothing here talks to Google.
"""

from dataclasses import dataclass
from datetime import datetime

from app.constants import TAIPEI, Kind, Leg, Status
from app.models import (
    PackingItem,
    PackingList,
    TransportNote,
    TransportOption,
    TransportRoute,
    Trip,
    TripLeg,
)
from app.services.domain.leg_types import enabled_labels, shows

# --- labels.js, mirrored ----------------------------------------------------

STATUS_LABELS = {"not_packed": "未打包", "packed": "已打包", "no_need": "不需打包"}
TIMING_LABELS = {
    "whenever": "隨時",
    "night_before": "出發前晚",
    "day_of": "出發當天",
    "just_before": "出發前",
}
NEED_LABELS = {"need": "需要", "bring": "需帶", "buy": "需買"}
LEG_LABELS = {"outbound": "去程", "return": "回程"}
ADVANCE_TICKET_LABELS = {True: "需要", False: "不需要"}
KIND_LABELS = {"template": "範本", "saved": "保存", "free": "一般"}
USAGE_LABELS = {"in_use": "使用中", "upcoming": "未來使用", "unused": "未使用", "past": "過去使用"}
TRANSPORT_TYPE_LABELS = {
    "hsr": "高鐵", "train": "火車", "metro": "捷運", "bus": "公車", "coach": "客運",
    "car": "開車", "bike": "腳踏車", "walk": "走路", "flight": "飛機", "ship": "船",
    "other": "其他",
}
RIDE_TYPE_LABELS = {
    "hail": "叫車", "own_car": "自駕自己的車", "car_rental": "租車",
    "own_bike": "自己的", "youbike": "YouBike", "moovo": "Moovo", "bike_rental": "租車",
}
TICKET_STATUS_LABELS = {"not_bought": "未買票", "not_needed": "無需買票", "bought": "已買票"}
DONE_LABEL = "已準備完成"
NOT_DONE_LABEL = "未準備完成"


def check_label(item: PackingItem) -> str:
    """Double Check is two fields; on screen it is one of three states."""
    if not item.needs_double_check:
        return "不需確認"
    return "確認" if item.double_checked else "未確認"


def status_label(row: PackingList | Trip) -> str:
    """`statusLabel`: the usage of a 一般 row, the kind of any other."""
    return USAGE_LABELS[row.usage] if row.kind == Kind.FREE else KIND_LABELS[row.kind]


# --- tab names --------------------------------------------------------------

OVERVIEW = "總覽"
TRANSPORT = "交通"
LIST_PREFIX = "清單 · "
TRIP_PREFIX = "行程 · "
MAX_TITLE = 90


def is_readable_title(title: str) -> bool:
    """A tab this backup owns and may delete: a list's or a trip's."""
    return title.startswith(LIST_PREFIX) or title.startswith(TRIP_PREFIX)


def tab_titles(prefix: str, rows: list) -> dict[int, str]:
    """Each row's tab name, by id: capped, and made unique in id order.

    Sheets compares tab names without regard to case, so the uniqueness check
    does too. A duplicate gets ` (2)`, ` (3)` and so on, the suffix fitting
    inside the cap rather than pushing past it.
    """
    taken: set[str] = set()
    titles = {}
    for row in sorted(rows, key=lambda r: r.id):
        base = f"{prefix}{row.name}"
        title, n = base[:MAX_TITLE], 1
        while title.casefold() in taken:
            n += 1
            suffix = f" ({n})"
            title = base[: MAX_TITLE - len(suffix)] + suffix
        taken.add(title.casefold())
        titles[row.id] = title
    return titles


# --- cells ------------------------------------------------------------------


def taipei(value: datetime | None) -> str:
    return value.astimezone(TAIPEI).strftime("%Y-%m-%d %H:%M") if value else ""


def _text(value) -> str | int:
    """A cell: null is blank, a number stays a number, anything else is text."""
    if value is None:
        return ""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return str(value)


def _tick(value: bool) -> str:
    return "✓" if value else ""


# --- layouts ----------------------------------------------------------------

ITEM_HEADERS = ["類別", "項目", "細節", "需求", "數量", "已打包數量", "單位",
                "打包狀態", "打包時機", "Double Check", "取得地點", "備註"]
LEG_HEADERS = ["出發地點", "目的地", "出發時間", "抵達時間", "類型", "方向", "交通工具", "車號",
               "座位", "價錢", "車票類型", "已訂票", "已付款", "已取票", "訂票代碼", "備註",
               "打包清單"]
TRANSPORT_HEADERS = ["目標起點", "目標終點", "交通工具", "提前買票", "方向", "起點", "終點",
                     "實際起點", "實際終點", "價錢", "時間", "班次間隔", "平日班次",
                     "假日班次", "路線圖", "時刻表", "即時動態", "備註"]


def list_matrix(packing_list: PackingList) -> list[list]:
    """The list's header block, a blank row, then its items in `position` order."""
    items = sorted(packing_list.items, key=lambda item: (item.position, item.id))
    settled = sum(1 for item in items if item.status != Status.NOT_PACKED)
    departure = packing_list.effective_departure_at
    return [
        [packing_list.name],
        ["狀態", status_label(packing_list)],
        ["出發", departure.isoformat() if departure else ""],
        ["去程/回程", LEG_LABELS.get(packing_list.leg, "")],
        ["備註", _text(packing_list.notes)],
        ["已處理", f"{settled} / {len(items)}"],
        [],
        ITEM_HEADERS,
        *(
            [
                _text(item.category),
                item.name,
                _text(item.detail),
                NEED_LABELS.get(item.need, ""),
                _text(item.quantity),
                _text(item.quantity_packed),
                _text(item.unit),
                STATUS_LABELS[item.status],
                TIMING_LABELS[item.timing],
                check_label(item),
                _text(item.location),
                _text(item.notes),
            ]
            for item in items
        ),
    ]


def _label_cell(leg: TripLeg, label: str) -> str:
    """✓ ticked, blank unticked, - when the entry does not show that label."""
    if label not in enabled_labels(leg):
        return "-"
    return _tick(getattr(leg, label))


def _shown(leg: TripLeg, field: str):
    """A field's value when the entry's type shows it; a hidden one is kept in
    the row but, as on screen, not shown."""
    return _text(getattr(leg, field)) if shows(leg, field) else ""


def _type_cell(leg: TripLeg) -> str:
    label = TRANSPORT_TYPE_LABELS[leg.transport_type]
    if leg.ride_type and shows(leg, "ride_type"):
        return f"{label} · {RIDE_TYPE_LABELS[leg.ride_type]}"
    return label


def leg_row(leg: TripLeg) -> list:
    return [
        leg.from_place,
        leg.to_place,
        taipei(leg.departs_at),
        taipei(leg.arrives_at),
        _type_cell(leg),
        _shown(leg, "direction"),
        _shown(leg, "service"),
        _shown(leg, "service_number"),
        _shown(leg, "seat"),
        _shown(leg, "price"),
        _shown(leg, "ticket_type"),
        _label_cell(leg, "booked"),
        _label_cell(leg, "paid"),
        _label_cell(leg, "collected"),
        _text(leg.booking_code) if leg.has_booking_code else "",
        _text(leg.notes),
        leg.packing_list.name if leg.packing_list else "",
    ]


def _leg_order(leg: TripLeg) -> tuple:
    """Departure order, undated entries last, then id: the screen's order."""
    return (leg.departs_at is None, leg.departs_at or datetime.min.replace(tzinfo=TAIPEI), leg.id)


def trip_matrix(trip: Trip) -> list[list]:
    """The trip's header block, then its legs in departure order: one block
    on a one-way trip, a 去程 block and a 回程 block on a round trip, each
    with its title and remark."""
    legs: list[TripLeg] = sorted(trip.legs, key=_leg_order)
    header = [
        [trip.name],
        ["狀態", status_label(trip)],
        ["準備", DONE_LABEL if trip.done else NOT_DONE_LABEL],
        ["車票", TICKET_STATUS_LABELS[trip.ticket_status]],
    ]
    if not trip.round_trip:
        return [*header, ["備註", _text(trip.notes)], [], LEG_HEADERS, *map(leg_row, legs)]
    sections = (
        (Leg.OUTBOUND, trip.outbound_title, trip.notes),
        (Leg.RETURN, trip.return_title, trip.return_notes),
    )
    rows = header
    for section, title, remark in sections:
        rows += [
            [],
            [LEG_LABELS[section], _text(title)],
            ["備註", _text(remark)],
            LEG_HEADERS,
            # A leg with no section on a round trip cannot be stored by the
            # API; one put there by hand reads as 去程, as the screen shows it.
            *(leg_row(leg) for leg in legs if (leg.section or Leg.OUTBOUND) == section),
        ]
    return rows


def departures_text(option: TransportOption, day_type: str) -> str:
    """`06:10 07:05 *08:15`: one day type's times, `*` marking an irregular one."""
    times = sorted((d for d in option.departures if d.day_type == day_type), key=lambda d: d.time)
    return " ".join(f"{'*' if d.irregular else ''}{d.time.strftime('%H:%M')}" for d in times)


def note_text(note: TransportNote) -> str:
    """`title · description · link link`: one route note on one line, its
    missing parts left out."""
    parts = [note.title, note.description, " ".join(link.url for link in note.links)]
    return " · ".join(part for part in parts if part)


def route_notes_text(route: TransportRoute) -> str:
    """The route's 備註, then each of its notes on a line of its own."""
    notes = sorted(route.note_entries, key=lambda n: (n.position, n.id))
    return "\n".join(text for text in [route.notes, *map(note_text, notes)] if text)


def transport_matrix(routes: list[TransportRoute]) -> list[list]:
    """One row per option, grouped by route.

    A route with no options gets a row of its own, so it is not lost. So does
    a route with 備註 or notes: the 備註 column belongs to the option on an
    option's row, and the route's own would otherwise have nowhere to go.
    """
    rows = [TRANSPORT_HEADERS]
    for route in sorted(routes, key=lambda r: (r.position, r.id)):
        options = sorted(route.options, key=lambda o: (o.position, o.id))
        notes = route_notes_text(route)
        if not options or notes:
            rows.append([route.from_place, route.to_place, *[""] * 15, notes])
        for option in options:
            rows.append([
                route.from_place,
                route.to_place,
                option.mode,
                ADVANCE_TICKET_LABELS[option.advance_ticket],
                _text(option.direction),
                _text(option.line_from),
                _text(option.line_to),
                _text(option.board_at),
                _text(option.alight_at),
                _text(option.price),
                _text(option.duration),
                _text(option.headway),
                departures_text(option, "weekday"),
                departures_text(option, "holiday"),
                _text(option.route_map_url),
                _text(option.timetable_url),
                _text(option.live_url),
                _text(option.notes),
            ])
    return rows


@dataclass(frozen=True)
class OverviewLink:
    """A row of 總覽 that links to a tab; the gid is known once the tab exists."""

    row: int  # 1-based
    title: str


def overview_matrix(backed_up_at: datetime, titles: list[str]) -> tuple[list[list], list[OverviewLink]]:
    """When the backup ran, then one row per readable tab.

    The rows hold the tab names as plain text; `links` says where they are so
    the caller can overwrite each with a `#gid=` link once it knows the gids.
    """
    matrix = [["Travel 備份"], ["備份時間", taipei(backed_up_at)], []]
    links = []
    for title in titles:
        matrix.append([title])
        links.append(OverviewLink(row=len(matrix), title=title))
    return matrix, links


def hyperlink(gid: int, title: str) -> str:
    """A link to another tab of this spreadsheet. Quotes in the name doubled."""
    return f'=HYPERLINK("#gid={gid}", "{title.replace(chr(34), chr(34) * 2)}")'
