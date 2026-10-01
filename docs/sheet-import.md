# Importing the owner's sheet

`scripts/import_sheet.py` loads the owner's Google Sheet into an empty
database. It is run once per database, not as a sync: a second run refuses.

## What the tabs become

Four tabs are read; any other tab is ignored. Tables are described in
[data-model.md](data-model.md).

| Tab | Becomes |
| --- | --- |
| `彰化回台北`, `台北去彰化` | Two packing lists forming a round-trip pair (`return` and `outbound`, sharing one `pair_id`), with their items in row order. Both are `saved`, so the three-list cap can never evict what the import loaded. |
| `Transportation` | Transport routes grouped by (`目標起點`, `目標終點`) in first-seen order, each with its options and departure times. |
| `This time` | One trip whose legs are the rows, each linked to the packing list for its journey: the list whose name, split at 去 or 回, has its first half starting the leg's 出發地點 and its second half starting its 目的地 (`彰化回台北` for 彰化火車站 → 台北車站). |

Columns are found by the text of the header row, so inserting a column in the
sheet does not break the import.

## Exporting

In the sheet: `File -> Download -> Microsoft Excel (.xlsx)`. Or fetch
`https://docs.google.com/spreadsheets/d/<id>/export?format=xlsx` while signed
in. **The export is never committed**: it carries booking codes. Keep it
outside the repository.

## Running

```bash
venv/Scripts/python.exe -m scripts.import_sheet export.xlsx --trip-start 2026-09-24 --dry-run
venv/Scripts/python.exe -m scripts.import_sheet export.xlsx --trip-start 2026-09-24
```

The `This time` tab's 時間 cell holds a weekday and two clock times, such as
`Thu 18:06-20:59`, and no date, so the date is supplied on the command line.
`--trip-start` is the date of the first `This time` leg, and its weekday must
match that leg's weekday (`Thu` for 2026-09-24) or the import stops. Each later
leg takes the next date on or after the previous leg with its own weekday.
Times are Asia/Taipei. `--trip-name` defaults to `彰化 ⇄ 台北`.

Everything is written in **one transaction**, committed once at the end: a
refusal or an error part-way through leaves the database as it was.
`--dry-run` parses, writes inside that transaction, prints the counts and the
notes, and rolls back.

The import **refuses, and writes nothing**, when the database already holds a
packing list with the same name, a route with the same two places, or a trip
with the same name. Every clash is printed.

Production is loaded from inside the container on the box, by the manager
session.

## What is skipped or changed, and what is refused

Everything skipped is printed as a `note:` line.

| In the sheet | In the app |
| --- | --- |
| An item named `無` | Skipped and reported. |
| A fully blank row | Ignored silently. |
| Blank `類別` or `項目` | Inherits the value above. |
| A Transportation row with a start and no end | Skipped and reported. |
| A Transportation row with no `交通工具` | Makes the route; its `時間` becomes the route note `時間 <value>`. |
| A departure cell `...` | No departures; the option note gains `<平日\|假日> <早\|中\|下午\|晚> 班次未知`, and it is reported. |
| A time in the wrong column (for example 11:35 under 中) | Imported, and reported. Boundaries are 12:00, 14:00 and 18:00. |
| A time listed twice for one option and day type | Kept once, and reported. |
| A departure cell that is a time, a date-time or a day fraction | Read as a time of day. A `*` prefix on a text time marks it irregular. |
| Identifiers such as `車號` and `訂票代碼` stored as numbers | Kept as text (`5158.0` becomes `5158`). |
| A leg with no matching packing list, or whose list another leg already took | Left unlinked and reported. |
| A blank `打包狀態`, `Double Check` or `打包時機` | Becomes 未打包, 不需確認 or 隨時 respectively, and the row is reported naming which columns were blank. |
| A leg whose arrival time is before its departure | Arrives the next day, and is reported. Equal times are refused. |
| A packing row with no `項目` and none above it | Refused with an error naming the tab and row. |
| A departure cell with an unreadable time | Refused with an error naming the tab, row, column and value. |
| An unknown status, timing, need, Double Check or booking word | Refused with an error naming the tab, row and value. |
| A `數量`, `已打包數量` or `價錢` that is not a number, such as 兩個 | Refused with an error naming the tab, row, column and value. |
