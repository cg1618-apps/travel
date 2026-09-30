# Sheet parity — design

Status: approved in conversation 2026-09-30, awaiting review of this written form.
Branch: `feat/sheet-parity`, cut from `refactor/spreadsheet-ui` with `dev` merged in.

## Intent

The owner plans travel in a Google Sheet. Four of its tabs are in scope —
`彰化回台北`, `台北去彰化`, `Transportation`, `This time` — and every other tab is
out of scope for this task. The goal is that the app can hold everything those
four tabs hold, and then holds their current data, so the app replaces them.

Success is: every non-empty row of the four tabs exists in the app, nothing the
sheet expresses is lost or squeezed into a field that cannot say it, and the
skips the importer makes are listed rather than silent.

Decided by the owner in conversation:

- **Both** schema/feature change and data import (not one or the other).
- Column C is an item **detail**, not a child item.
- `需求` is a real closed field of three values; `取得地點` is an open,
  per-item value.
- `*` on a departure time means "that run does not always operate".
- A trip leg **links** a packing list; the trip does not own the list pair.
- The `This time` trip is in the past: Thursday 2026-09-24 and Monday
  2026-09-28.

## Sequencing

One branch, one PR. The new packing columns land in the sheet UI that
`refactor/spreadsheet-ui` introduced, which has not been merged and which the
owner has not yet seen running. **Before building on it, the app is started on
this branch and the owner looks at the sheet UI.** If it is rejected, this spec
is revisited before anything else is built on it.

## 1. Packing items

One Alembic migration adds three nullable columns to `packing_item`.

| Sheet column | Field | Notes |
| --- | --- | --- |
| 類別 | `category` | existing, free text |
| 項目 (B) | `name` | existing. A blank B cell inherits the B above it. |
| C | **`detail`** | new, text, nullable. `鑰匙` + `家鑰匙` and `鑰匙` + `宿舍鑰匙` are two items sharing a name. Holds variants and descriptions alike (`long c-c beside bed`). |
| 數量 | `quantity` | existing |
| 已打包數量 | `quantity_packed` | existing; blank imports as 0 |
| 打包狀態 | `status` | 未打包 `not_packed`, 已打包 `packed`, 不需打包 `no_need` |
| Double Check | `needs_double_check`, `double_checked` | 不需確認 → false/false, 未確認 → true/false, 確認 → true/true |
| 打包時機 | `timing` | 隨時 `whenever`, 出發前晚 `night_before`, 出發當天 `day_of`, 出發前 `just_before` |
| 需求 | **`need`** | new, text, nullable, closed: `need` 需要, `bring` 需帶, `buy` 需買. `ck_packing_item_need` with an explicit null arm, like `ck_packing_list_leg`. |
| 取得地點 | **`location`** | new, text, nullable, open. Suggested by `label_option`, which gains kind `location`. |
| 備註 | `notes` | existing |

Meaning of `need`: `bring` — already owned, taken from `location`; `buy` — to be
bought, at `location`; `need` — needed, with bring-or-buy not yet decided.

- `label_option.kind` becomes `category`, `bag`, `location`, `ticket_type`
  (the last is for trip legs, §3). The check constraint is widened in the same
  migration. The existing rules — saving records the value, renaming rewrites
  users of it, renaming onto an existing option merges, deleting leaves users
  alone — apply to every kind, each against the table and column that kind
  belongs to.
- Copying a list carries `detail`, `need` and `location` (definition), and
  resets packed state as today.
- `bag` stays; the sheet does not use it.
- The sheet UI gains **Detail**, **Need** and **Location** columns. The
  checklist shows `name · detail` on the first line and need and location on
  its quiet second line.

## 2. Transportation

Three tables.

**`transport_route`** — `id`, `from_place` (text), `to_place` (text), `notes`,
`position`, timestamps. A route with no options is valid.

**`transport_option`** — one way of doing a route. `route_id` FK
`ON DELETE CASCADE`.

| Sheet | Field | Type |
| --- | --- | --- |
| 交通工具 | `mode` | text, not null |
| 提前買票 | `advance_ticket` | boolean, default false; 需要 → true, 不需要/blank → false |
| 路線圖 | `route_map_url` | text, nullable |
| 時刻表 | `timetable_url` | text, nullable |
| 即時動態 | `live_url` | text, nullable |
| 方向 | `direction` | text, nullable |
| 起點 / 終點 | `line_from`, `line_to` | text, nullable — the line's own terminals |
| 實際起點 / 實際終點 | `board_at`, `alight_at` | text, nullable — where you get on and off |
| 價錢 | `price` | integer NT$, nullable |
| 時間 | `duration` | text, nullable (`7m`, `2h-2h30m`) |
| 班次間隔 | `headway` | text, nullable |
| — | `notes`, `position`, timestamps | |

**`transport_departure`** — `option_id` FK `ON DELETE CASCADE`, `day_type`
(`weekday` / `holiday`, `ck_transport_departure_day_type`), `time` (time),
`irregular` (boolean, default false), unique on (`option_id`, `day_type`,
`time`).

The sheet's four columns per day type — 早, 中, 下午, 晚 — are a display. The
screen buckets by clock: 早 before 12:00, 中 12:00–13:59, 下午 14:00–17:59,
晚 from 18:00. The importer verifies each imported time lands in the bucket of
the column it came from and reports any that do not, rather than trusting the
boundaries silently.

Screen: a **Transport** page listing routes; a route shows each option as a
card (stops, price, duration, links) with its departures as a weekday row and a
holiday row, grouped 早/中/下午/晚. Irregular times are visibly marked; the next
departure from now for today's day type is highlighted. Editing is in place,
enter/blur commits, escape reverts, no save button — the sheet UI's rules.

Weekday vs holiday for "today" is Monday–Friday vs Saturday–Sunday. Public
holidays are not modelled.

## 3. This time (trips)

**`trip`** — `id`, `name`, `notes`, timestamps.

**`trip_leg`** — `trip_id` FK `ON DELETE CASCADE`.

| Sheet | Field | Type |
| --- | --- | --- |
| 出發地點 / 目的地 | `from_place`, `to_place` | text, not null |
| 時間 | `departs_at`, `arrives_at` | timestamptz, not null; entered and shown in Asia/Taipei. `ck_trip_leg_arrives_after_departs`. |
| 時長 | — | derived from the two, not stored |
| 車種 | `service` | text, nullable |
| 車號 | `service_number` | text, nullable — an identifier |
| 座位 | `seat` | text, nullable |
| 價錢 | `price` | integer, nullable |
| 車票類型 | `ticket_type` | text, nullable, suggested by `label_option` kind `ticket_type` |
| 訂票狀態 | `booked`, `paid`, `collected` | three booleans, default false |
| 訂票代碼 | `booking_code` | text, nullable — leading zeros survive |
| 備註 | `notes` | text, nullable |
| — | `packing_list_id` | FK `packing_list.id` `ON DELETE SET NULL`, nullable, **unique** |

**The current trip** is the trip with the earliest leg whose `departs_at` is in
the future; if no trip has one, the trip whose latest `arrives_at` is most
recent; ties broken by `trip.id` descending. A trip with no legs is never
current. Lives in `app/services/domain/trip.py`.

**Departure source.** A packing list linked from a leg takes its departure date
from the leg — `departs_at` as a calendar date in Asia/Taipei — and its own
`departure_at` is ignored while linked. The list response carries
`departure_source: "list" | "trip_leg"`; the list screen shows the date as set
by the trip rather than as editable. An unlinked list behaves exactly as today.
This supersedes the earlier intention (in the packing migration's docstring) of
a `trip_id` on `packing_list`; `notes/decisions.md` records why.

Screen: a **This time** page with the current trip on top, its legs as cards in
time order — departure → arrival, duration, service and seat, the booking code
large with tap-to-copy, booked/paid/collected as three ticks, and a link to the
leg's packing list — and past trips below as a plain list.

## 4. Import

`scripts/import_sheet.py <file.xlsx> [--dry-run]`, following media's
`scripts/` convention. `openpyxl` goes into `requirements.txt` so the same
script runs inside the production container later.

- Reads the four tabs by name and nothing else. The export is never committed —
  it carries booking codes.
- Refuses before writing if any list, route or trip it would create already
  exists by name/places, naming each clash. One transaction; all or nothing.
- `--dry-run` prints the plan and the skip report and writes nothing.

What it creates:

- Two packing lists, `彰化回台北` and `台北去彰化`, as a round-trip pair
  (`彰化回台北` `return`, `台北去彰化` `outbound`), `saved` so the cap cannot
  evict them. Positions follow sheet order.
- Routes, options and departures from `Transportation`.
- One trip, `彰化 ⇄ 台北`, with two legs:
  - 2026-09-24 18:06–20:59 彰化火車站 → 台北車站, 火車 - 自強, 5158, 5車15號,
    550, 電子, booked/paid/collected, linked to `彰化回台北`.
  - 2026-09-28 12:15–14:23 台北車站 → 彰化火車站, 火車 - 自強 (3000), 137,
    3車31號, 550, 電子, booked/paid/collected, linked to `台北去彰化`.

Sheet quirks and what happens to each:

| Quirk | Handling |
| --- | --- |
| Blank B cell | inherits the B above it; blank A inherits likewise |
| Item named `無` | skipped — "nothing in this category"; reported |
| Numbers read as floats (`1.0`, `5158.0`) | integers, or integer text for identifiers |
| A time cell stored as a day fraction (`0.538…`) | converted to a time |
| `*` prefix on a time | `irregular = true` |
| `...` in a time cell | no departures; a note on the option saying that column is unknown; reported |
| `彰化火車站 → 台北車站` row with only a duration | a route whose `notes` carry the duration |
| `新烏日火車站` row with no destination | skipped; reported |
| Route rows with no mode (`宿舍 → 彰化火車站`) | a route with no options |

The importer is run against the local `travel` database on this branch.
Production is a manager-session step after release — this machine cannot reach
the box — and the release PR says so.

## 5. API

Routers follow the existing packing routers' shape and error conventions.

- `/api/transport-routes` — CRUD; reads nest options and their departures.
- `/api/transport-options`, `/api/transport-departures` — create, update,
  delete.
- `/api/trips` — CRUD; reads nest legs. `/api/trips/current` — the current
  trip, or 404 when there is none.
- `/api/trip-legs` — create, update, delete. Linking a list already linked
  elsewhere is a 409.
- `/api/packing-items` accepts `detail`, `need`, `location`.
- `/api/packing-lists` responses carry the effective `departure_at` and
  `departure_source`.

## 6. Testing

TDD throughout, full runs under the machine-wide pytest lock.

- Router tests for every endpoint above.
- Refusal tests on non-empty data, each with its mirror built from the same
  fixture: an invalid `need`; an invalid `day_type`; arrival before departure;
  a list linked from two legs; an import into a database that already holds
  one of its targets.
- The current-trip rule: future beats past, earliest future leg wins, most
  recent past wins, a leg-less trip is never current, the id tie-break.
- Departure source: linked uses the leg's Taipei date (a leg at 00:30 Taipei is
  the previous UTC day — the test that makes the timezone bite); unlinked uses
  its own.
- The migration runs from zero against the scratch database, and downgrades.
- The importer against an `.xlsx` built inside the test carrying every quirk in
  §4's table, asserted field by field.
- Vitest: the 早/中/下午/晚 bucketing at its boundaries, and duration display.

## 7. Docs

In the same commit as the behaviour: `data-model.md`, `api.md`,
`business-rules.md` (current trip, departure source, need and location, the
copy table), `frontend.md`, `notes/decisions.md` (item + detail, `need` closed
vs `location` open, departures as rows not columns, leg-links-list over
trip-owns-pair and over `packing_list.trip_id`, the importer shipping in the
image), and the status paragraph in `docs/README.md`. This spec and its plan are
deleted when the task ends.
