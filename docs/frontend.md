# Frontend

Last verified: 2026-10-03

**What this is for.** How the React app is laid out, where each kind of thing
lives, and the decisions a new screen has to follow. The endpoints it calls are
in `api.md`; the rules it renders are in `business-rules.md`.

## Layout

| Directory | What lives there |
| --- | --- |
| `src/api/` | `client.js` — the only place that calls `fetch()`. `endpoints.js` — every URL in one map. |
| `src/hooks/` | `useApiQuery.js` — TanStack Query over `fetchJson`, plus `useApiMutation` and `send`. `useLongPress.js` — a long-press that never also fires the click. `useTheme.js` — light or dark, and the toggle. |
| `src/pages/` | One file per screen, PascalCase, default export. |
| `src/components/` | `Grid` and `GridRow` (the sheet, and one row of it), `NewRows`, `FilterMenu`, `GroupOrderDialog`, `Sortable`, `Combobox`, `Checklist`, `Cell`, `PriceCell`, `RowMenu`, `ConfirmDialog`, `EvictDialog`, `KindControls`, `IndexTabs`, `TripCalendar`, `States`, `Segmented`, `NoteEditor`. |
| `src/lib/` | Pure modules with no React in them. Tests sit beside them. |

Routes are declared in `src/App.jsx`: `/` the dashboard, `/lists` and
`/lists/:listId` the packing lists, `/transport` and `/transport/:routeId`
交通, `/trips` and
`/trips/:tripId` 行程, `/notes` 筆記, `/options` 選項. Two old addresses redirect, so a
bookmark still lands: `/trip` to `/trips`, and `/trips/auto-saved` to
`/trips?tab=auto_saved` (declared above `/trips/:tripId`, which would otherwise
read it as an id). Any other path renders the dashboard.
The nav bar names 打包清單, 行程, 交通, 筆記 and 選項, ends with the theme toggle, and the app's name `travel` links to `/`.

**The nav bar is sticky**, and holds one height, `--nav-h` in `index.css`:
on a screen too narrow for every name, the names scroll sideways and the toggle
stays put, rather than the bar wrapping to a second row. Anything else that
sticks to the window pins below it with `top-[var(--nav-h)]`, which
`nav-offset.test.js` guards. It sits at `z-40`, over the sticky headers and
under the `z-50` dialogs and menus.

Every screen is editable, so every one of
them goes through TanStack Query — media's split is query hooks for anything
written back from the UI and plain `fetch` for read-only pages, and this app has
no read-only pages.

## The screen speaks the sheet's language

**Every string a person sees is Traditional Chinese**, in the owner's Google
Sheet's own words, except `Double Check`, which the sheet itself writes in
English, and the app's name `travel`. The two screens named after the sheet's
English tabs are 交通 (`Transportation`) and 行程 (`This time`). `index.html` says
`lang="zh-Hant-TW"`.

**Stored values stay English enum text** (`not_packed`, `night_before`,
`bring`). The mapping from a stored value to what the screen says lives in
**`src/lib/labels.js` and nowhere else** — a component that needs 已打包 imports
`STATUS_LABELS`, it does not spell it. `labels.test.js` walks every vocabulary,
so a value with no display string fails a test rather than rendering blank.

**Kinds and 狀態 have their labels there too**: `KIND_LABELS` (範本, 保存,
一般), `AUTO_SAVED_LABEL` (自動保存, which is not a stored kind) and
`USAGE_LABELS` (使用中, 未來使用, 未使用, 過去使用). The rules the screens share
about them — which badge a row gets, which rows the dashboard shows, the
limits shown as `n / 5` and `n / 10`, every row of an index once, the tabs
(`TABS`, `tabFromSearch`, `tabFor`, `tabCounts`), the name a source fills in
(`autofillName`) and the leg picker's choices and labels (`linkChoices`,
`linkLabel`, `statusLabel`) — are pure helpers in `lib/kinds.js`, tested
beside it.

**A trip entry's vocabularies are there as well**: `TRANSPORT_TYPE_LABELS`
(高鐵, 火車, 捷運, 公車, 客運, 開車, 腳踏車, 走路, 飛機, 船, 其他, in
`TRANSPORT_TYPES` order), `RIDE_TYPE_LABELS`, `TICKET_STATUS_LABELS` (未買票,
無需買票, 已買票), `ROUND_TRIP_LABELS` (單程, 來回), `BOOKING_LABELS` (已訂票,
已付款, 已取票), `DONE_LABEL` / `NOT_DONE_LABEL` (已準備完成, 未準備完成) and
`ENDED_LABEL` (已結束). What each 類型 shows is not a label but a table — see
"行程 detail".

**An API `detail` is never rendered.** It is English by contract (`api.md`).
`ErrorState` says 發生錯誤。 with the status code; `EvictDialog` writes its own
body and takes the names from `evict_next`.

## Two views, and why there are exactly two

A packing list is used for two different jobs, and one screen cannot do both
well.

- **表格, the sheet** (`components/Grid.jsx`) is where a list is *planned*. Every column
  is visible, every cell edits where it sits, rows sit in their 類別 and
  five columns filter. It is what you would build in a spreadsheet, because
  that is what people do build.
- **清單, the checklist** (`components/Checklist.jsx`) is where a list is
  *worked through*. A tick, a name, a quiet second line, one place to add, and
  finished things folded away under 已完成. Nothing is edited in place; the
  tick and the row menu are all it offers.

The switch names the two views. **It does not offer an axis to group by.** An
earlier version put "When / Category / Bag" on screen — internal vocabulary
from the data model, asked as a question of someone who wants to pack a bag.
Grouping is not a thing a person wants; seeing their list is. The sheet does
group, but always by 類別 and without asking — that is how the owner's own
sheet is laid out — and the filters cover finding things without a question.

The choice is remembered in `localStorage`, and a first visit on a narrow
screen starts on Checklist, because a sheet at 375px is a horizontal scrollbar.

## The dashboard

`/` (`pages/Dashboard.jsx`) shows what is in use now and edits nothing. It
reads the indexes the other screens already own — `['packing-lists']` and
`['trips', 'index']` — so a write anywhere refreshes it.

- **The calendar** (`components/TripCalendar.jsx`) is first: one month,
  Sunday first (日 … 六), six weeks with the neighbouring months' days faded,
  opening on the current Taipei month with today circled. ‹ and › change the
  month; 今天 comes back to this one and shows only when away from it. Every
  Taipei day from a trip's first time to its last is shaded — an entry with
  only one time counts it as both its ends, and a trip with no times is not
  marked — and links to the trip, with its name under the date on a wide screen and a dot
  on a narrow one; a day two trips share names both and links to the first.
  Every trip but templates is marked, whatever its kind or 狀態 — a 範本's
  dates are only where a copy starts. The day arithmetic (`monthGrid`,
  `tripDays`, `taipeiToday`, `shiftMonth`) is in `lib/calendar.js`, tested
  beside it.

- **The order** of both sections is `onDashboard` in `lib/kinds.js`: 一般 rows
  that are 使用中 or 未來使用, **soonest start first**, a row with no start
  after every row with one, and rows that tie in the order the index gave them.
  A trip starts at its earliest entry departure; a list at its 出發 date (the
  API's effective `departure_at`) at Taipei 00:00 (`rowStart`). `on_dashboard`
  in `app/services/domain/dashboard.py` is the same rule for the sheet backup,
  and `kinds.test.js` (`DASHBOARD_CASES`) and
  `tests/unit/test_dashboard_rule.py` pin the two to the same cases.
- **已結束** marks a row whose end has passed (`hasEnded`, frontend only): a
  trip's latest arrival, else departure; a list linked from an entry with a
  time, that entry's arrival, else departure — found through the trips index
  (`legsByList`); any other list, the end of its 出發 day in Taipei. A row
  with no end gets no badge.
- **清單** — those lists, each with its 狀態 badge. Each row links to the
  list and shows its 出發 (`departureLabel` in `lib/timing.js`, shared with
  the index) and `已處理 {settled} / {items}`. 所有清單 links to `/lists`.
- **行程** — those trips, each with its 狀態 badge, 已結束 when it applies,
  **已準備完成** or **未準備完成** (the `done` flag), and **已買票** or
  **未買票** — nothing for 無需買票 (`readinessBadges` in `lib/trips.js`) —
  then its date range or 沒有行程段, linking to `/trips/{id}`. The date range
  counts an entry with one time on that time, and is 沒有行程段 when no entry
  has a time.
  所有行程 links to `/trips`. There is no current trip and no 目前 badge.
- **Nothing else, and nothing to add.** Beyond the calendar's marks, 自動保存,
  保存 and 範本, and every create form, belong to `/lists` and `/trips`; the dashboard only links there.
  An empty section says so plainly (目前沒有使用中或未來使用的清單。 /
  目前沒有使用中或未來使用的行程。) and offers nothing.

## The index tabs

`/lists` and `/trips` both open on `components/IndexTabs.jsx`, a browser-style
tab strip: **一般（n）· 範本（n）· 保存（n）· 自動保存（n / 5）**, or `n / 10`
for trips. The active tab joins the panel below it. The tab is held in the URL
as `?tab=` — `template`, `saved` or `auto_saved`, and absent for 一般 — so Back
and a reload come back to it; anything else reads as 一般 (`tabFromSearch`).
Each tab is one of the API's four arrays, shown as it comes rather than filtered
again, so every row is on exactly one tab. An empty tab says how a row gets
there, in one line.

The strip scrolls sideways on a narrow screen. Its baseline is drawn by an
inner `min-w-max` row inside the scroller, not by the scroller itself: the
active tab's `-mb-px` then overlaps that row's border — which is what joins it
to the panel — instead of overflowing a box whose `overflow-x-auto` also makes
it scroll vertically.

## Creating from a source fills the name

On both create forms, choosing a source to copy — 從哪份清單複製項目 on
`/lists`, 從範本 on `/trips` — fills 名稱 with the source's name, a trailing
`（範本）` removed (templates made before 當作範本 kept the name carry one), but only while the field is empty or still holds the
previous fill (`autofillName`). A typed name is never overwritten; going back to
no source (空白開始, 不使用範本) clears only a fill.

## 打包清單 (`/lists`)

`pages/PackingLists.jsx` shows each tab as a table:

- **一般** — each row has `KindControls`: a 狀態 select, a 保存 checkbox and a
  當作範本 button.
- **自動保存** — the same row; 狀態 reads 過去使用, and changing it returns
  the list to 一般. The first line of 保存備註 sits under the name.
- **保存** — the 保存 checkbox and 當作範本, and the first line of 保存備註.
- **範本** — no controls: a template's kind never changes and it has no 狀態.

The first line of 保存備註 shows on 保存 and 自動保存 rows only. **+ 新增清單**
opens a form with 名稱, 出發日期, 類型 (一般 or 範本) and 從哪份清單複製項目,
which offers every list once, any kind, with its badge.

**當作範本** creates a template of the same name — the 範本 badge already says
what it is — with the items copied and shows a notice
linking to it, dismissed with 知道了. **Unticking 保存** asks first, in
`KindControls` itself so every place that shows the checkbox asks the same
question: 取消保存後會回到一般清單（未使用）。 **過去使用 into a full 自動保存**
opens `EvictDialog` (see "The 409 is a decision").

## The sheet's columns

In the sheet's order: **類別 · 項目 · 數量 · 已打包數量 · 打包狀態 · Double
Check · 打包時機 · 需求 · 取得地點 · 備註**, then a ⋯ column for the row menu.
項目 spans two cells: the name, and its `detail` beside it.

Before them come **#**, the row number, and a grip column (⠿) for dragging a
row; see "Groups and order". The number is the row's place in the whole list in
the order the sheet shows it (`rowNumbers` in `lib/grouping.js`), so a filter
leaves gaps rather than renumbering and a drag renumbers. New rows continue the
count. **#** is pinned to the left edge while the sheet scrolls sideways; its
cell is painted on the canvas so nothing shows through, and its right edge is a
shadow, since a collapsed border scrolls away with the table.

The header row is sticky. On a screen wide enough for the whole sheet the page
scrolls and the header sticks just below the nav bar; on a narrower one the
sheet scrolls sideways inside its own box, which then also scrolls vertically
(at most the screen the nav bar leaves) so the header can stick to that box's top. A sticky
element sticks to its nearest scroll container, and an `overflow-x` box is one
whether or not it scrolls vertically.

**刪除模式** on the sheet's toolbar puts a checkbox in place of each row's grip,
with 全選 and 刪除所選（n）, disabled with nothing ticked or while a delete is in
flight. That opens one `ConfirmDialog` naming every selected item; confirming
calls `POST /api/packing-lists/{id}/items/bulk-delete`, and a failure shows
無法刪除，請再試一次。 完成 leaves the mode and clears the selection. **Only what
the filters show can be deleted**: 全選 takes the rows on screen, and a row ticked
and then filtered out drops out of the count, so nothing goes unseen. Rows cannot
be dragged in the mode. The checklist has no such mode; it is for working through
a list, and offers the tick and the row menu alone.

**Colour says the value.** 打包狀態, Double Check, 打包時機, 需求 and 取得地點
tint their whole cell, a sheet's conditional colour (`lib/tones.js`, classes
`tone tone-*` in `index.css`). Green is done (已打包, 確認), amber is waiting on
you (未確認), 打包時機 warms as it gets closer to leaving (隨時 grey, 出發前晚
violet, 出發當天 orange, 出發前 rose), and 需求 is sky / teal / pink. 不需打包
and 不需確認 are deliberately plain. 取得地點 is open text, so its tone is a hash
of the text: the same place is the same colour on every list. A tone is one hue
mixed with the theme's text colour and laid thin over the surface, so one rule
reads in both themes.

**Filters** sit in the headers of 打包狀態, Double Check, 打包時機, 需求 and
取得地點 (`components/FilterMenu.jsx`, rules in `lib/filters.js`): Google
Sheets' "filter by values", a tick per value, nothing ticked meaning no filter.
Values within a column are ORed, columns ANDed; an unset 需求 or 取得地點 is
（空白） and can be ticked too. 取得地點 offers only the places the list
holds. A filtered sheet says 篩選中：顯示 n / m 項 above it with 清除所有篩選,
and cannot be dragged — a drop between two visible rows says nothing about
where the hidden ones go. There is no sorting: the sheet is always in its own
order.

Two shortcuts onto those same filters sit above the sheet, beside 排序類別.
**未打包 / 未完成 / 全部** sets the 打包狀態 filter to exactly 未打包, or clears
it; it is read back off that filter (`statusScope`), so it shows neither when the
header holds any other choice. **打包時機** is the column's four values as chips,
ticking the same filter as its header. Neither is a filter of its own, so the
header and the toolbar cannot disagree.

**未完成** is the exception: a row that is 未打包 **or** 未確認 (`isUnfinished`),
so a 不需打包 row still waiting on its Double Check is shown. Columns combine
with AND, so no header filter can say it, and it is a flag of its own
(`unfinished`) beside them. Choosing it clears the 打包狀態 filter; choosing
未打包 or 全部 turns it off. While it is on the switch shows 未完成 whatever the
headers hold, and a header filter narrows it further. It counts as filtering,
and 清除所有篩選 clears it with the rest. Like the header filters, none of this
is remembered: the sheet opens on 全部.

**`bag` is not shown.** The sheet has no such column. The field stays in the
data and in the copy rule, and its remembered values are still managed on the
選項 screen; nothing on the sheet reads or writes it.

## Variants: split rows, grouped on screen

Every row is its own item. `鑰匙 · 家鑰匙` and `鑰匙 · 宿舍鑰匙` are two items
sharing a name, each with its own status.

Rows come from `groupRuns` in `lib/grouping.js`, run inside each 類別: 類別
is written only on a group's first row and 項目 only on the first row of a run
of equal names, the cells beneath left blank — how the Google Sheet reads. A row
continuing a name run has a lighter top border, so an item and its variants read
as one block. A blank cell is still a cell: clicking it opens the editor on the
value the row really holds.

**新增變化** in the row menu inserts a new item directly below the row,
carrying its `category` and `name` (`after_id` on item create — see `api.md`).
Grouping then blanks both, so the variant appears in place, waiting for its
`detail`.

The checklist groups the same runs with `groupForChecklist`: a group of one is
a single line (`name · detail`), in the same 類別 order as the sheet
(`inGroupOrder`); a group of several is the name as a heading
with each variant indented beneath it, each with its own tick. 未打包 items and
finished ones are grouped separately, so a group can appear in both halves.
The quiet second line is 需求, 取得地點, `已打包 {packed} / {quantity}{unit}`
(— for a count nobody has entered)
and 備註, joined with ` · `; an outstanding Double Check adds a 待確認 link that
marks it confirmed.

## Groups and order

**A group is a 類別, and a group is always together.** `groupByCategory` puts
every item of one category in one group — items with no category form a group
of their own, labelled （未分類） where it needs a name — ordered by position,
and orders the groups by where their first item sits. Each group is its own
`<tbody>` with a strong border round it, so where one 類別 ends is visible
without reading the cells. The server keeps the same rule on its side: a new
or re-categorised item goes to the end of its group, and an order that splits a
group is refused (`api.md`).

**Rows are dragged within their group**, by the ⠿ grip beside the row number
(`components/Sortable.jsx`, the media tracker's dnd-kit wrapper: pointer events
rather than HTML5 drag, which swallows the wheel on Windows and does nothing on
touch; a short hold on touch so a swipe still scrolls). Focusing the grip and
pressing ↑ / ↓ moves a row one place. A drop never leaves its group.

**Groups are ordered in 排序類別**, a dialog of their own
(`GroupOrderDialog.jsx`), so a drag on the sheet only ever means a row. Nothing
is saved until its 儲存. Each list keeps its own order, including of categories
another list also has, because the order is that list's item positions. The same
dialog is 排序群組 on 交通, given its own title, hint and group name. 筆記 orders
its groups with arrows instead.

Both write the list's whole order in one `PUT …/order`, built by `orderIds`.
The page applies it to the cache first, so a dropped row stays where it was
dropped during the round trip; the response replaces the cache, and a refusal
puts the server's order back with 排序沒有儲存，已還原。

## Adding rows

**▸ 新增一列… opens new rows in place, every column editable, and nothing is
saved until 儲存 n 列** (`components/NewRows.jsx`, rules in `lib/drafts.js`).
That is the exception to "no Save button", and the reason for it: a row saved
the moment its 類別 was typed would jump into its group, and the rest of it
would have to be found again. Kept until 儲存, it lands in its group complete.

Each field is placeholdered with its column's name, and 數量 is one box split
into 數量 | 單位, as its cell is — with a minimum width of its own, since the
table would otherwise squeeze the two inputs to slivers.

＋ 再加一列 adds another, starting in the 類別 of the row above it. A row
left untouched is skipped; a row with no 項目, or a 數量 / 已打包數量 that is
not a whole number, stops the save and is outlined. Ctrl+Enter (⌘+Enter) saves;
取消 drops them all. The save is one `POST …/items/bulk-create`, all or
nothing, and a failure keeps every typed row on screen.

The checklist keeps its one-line ⊕ 新增項目, which creates the item at once
with only a name.

## 打包狀態: three stored, two tapped

All three values stay in the data — 不需打包 is a decision, and folding it into
未打包 would make it indistinguishable from forgetting. But a tap only ever
means *packed*:

- **One tap** — the 打包狀態 cell in the sheet, the tick in the checklist —
  toggles 未打包 ⇄ 已打包 (`tapStatus` in `lib/status.js`). A 不需打包 row, shown
  greyed and struck through, returns to 未打包 on one tap.
- **不需打包 is one step further**: a long-press (500 ms) on that cell or the
  tick, or the row's ⋯, opens `RowMenu`. `useLongPress` makes sure the click
  that follows a long-press does nothing, so one gesture never does both. A
  keyboard click (Enter or Space) is never swallowed. The menu itself ignores
  clicks until it has seen a pointer down or a key of its own, because the
  click that ends a long-press touch lands wherever the finger is — on iOS
  Safari, the backdrop or a menu item — and must neither close the menu nor
  pick from it.

The row menu is built once, by `rowActions` in `lib/rowMenu.js`, so both views
offer the same things: 設為不需打包 (or 改回未打包), 新增變化, and 刪除 — the
sheet's old ✕ column lives here now. The checklist's menu also holds the three
Double Check states, since the checklist has no Double Check column. On a wide
screen the menu opens beside the row; on a phone it is a bottom sheet.

刪除 asks first, and the question names the item the way a person does — 名稱
and 細節 together, 刪除「鑰匙 · 家鑰匙」？, or just the 名稱 when there is no
細節 — because two variants of one item differ only by their 細節.

## 重設狀態

A button in the list header, behind a `ConfirmDialog`. It calls
`POST /api/packing-lists/{id}/reset`: 已打包 → 未打包, 已打包數量 cleared to —, Double
Check back to 未確認. **不需打包 is left alone** — it is a choice about the
list, not progress through it. The rule itself is the server's
(`business-rules.md`).

## The list header

**The name is a cell**, edited by clicking it like any other, and it cannot be
emptied: a blanked name keeps its value rather than sending a null the API
would refuse. Beside it, ⋯ 刪除清單 asks first, saying the items go with the
list and a 行程 leg that linked it is kept, only unlinked. Deleting
returns to `/lists`. The ⋯ is `components/DeleteMenu.jsx`, shared with the
route, card, trip and leg menus.

`lib/listHeader.js` builds both lines, pure so the day boundaries are tested:
`未設定日期`, `今天出發`, `明天出發`, `{n} 天後出發`, `已出發 {n} 天`, each
followed by the date; and progress as `已處理 {s} / {n}`, `{u} 項待確認`,
`可以出發了`. A list's own date is edited by clicking it. A date that comes from
a 行程 leg (`departure_source: "trip_leg"`) says so — `由行程設定` — and is not editable here, because it is changed on the leg.

Under the date the header carries the list's kind: a 範本 / 保存 / 自動保存
badge, and the same `KindControls` as its row on `/lists`. 當作範本 here opens
the new template. On a 範本 the same row holds **+ 從這份範本建立清單**
(`components/CreateFromTemplate.jsx`): it opens a name, already filled from the
template, and an optional 出發日期, and 建立 makes a 一般 list with the
template's items and opens it. Then a **備註** cell, and a **保存備註** cell when
the list is saved or auto-saved or already has a remark — both multi-line
(`TextAreaCell`, below). 過去使用 into a full 自動保存
opens the same `EvictDialog`; the index it names from is fetched only once a
refusal has happened, and the dialog opens only once that read has arrived
fresh, so it never names a list from a stale `evict_next`.

## Spreadsheet conventions, because that is the reference

`components/Cell.jsx` implements the bargain every spreadsheet makes, so nobody
has to be told it:

- **Click a cell to edit it.** No pencil icon, no edit mode, no modal.
- **Enter or blur commits. Escape reverts.** Escape has to be safe — it is what
  people press when they realise they clicked the wrong cell.
- **There is no Save button** on an existing row. New rows are the one
  exception — see "Adding rows".
- **Every cell is one line, except a remark.** A wrapping cell changes the row
  height and makes the sheet ripple while you type; the sheet scrolls sideways
  instead.

**A remark is several lines: `TextAreaCell`.** Every remark field uses it — a
trip's 備註 (and 去程備註, 回程備註), 保存備註 on a trip or a list, an entry's
備註, a list's 備註, a packing item's 備註 on the sheet, a route's and an
option's 備註, and a note's 說明 on a route and on 筆記. It shows its text with
the line breaks kept; clicking opens a textarea. **Enter is a new line**, so
Ctrl+Enter (⌘+Enter) or leaving the cell commits, and Escape reverts. Trailing
blank lines are dropped and nothing but whitespace saves as null (`remarkValue`
in `lib/cells.js`).

**Every multi-line field is an `AutoGrowTextarea`**
(`components/AutoGrowTextarea.jsx`): as tall as its text, growing and shrinking
while you type, never scrolling inside itself. That is `TextAreaCell`'s editor,
the 說明 in the note form, which starts at three lines (`rows`), and 備註 in the
sheet's new rows.

數量 is one cell holding the target and its unit — "5 雙" is one fact.
The number must be whole: anything else (`1.5`, `兩`) reverts the cell and
sends nothing, unit included, the way 價錢 refuses a typo; an emptied number
clears it. 已打包數量 refuses the same way, and an emptied one is cleared. All
three cells read their text with `parseWholeNumber` in `lib/numbers.js`.
已打包數量 is its own cell, as in the sheet. It shows — until someone enters a
count, like 數量, so a blank never reads as "none packed"; once there is a
count it turns amber when short of 數量, because being short is the failure a
packing list exists to catch.

Double Check is one select with three positions — 不需確認, 未確認, 確認 —
rather than two checkboxes. It maps onto `needs_double_check` and
`double_checked` (`CHECK_FIELDS` in `labels.js`). 需求 is a select whose empty
option (—) stores null; `SelectCell` treats `''` as null for any column that
may be unset. 取得地點 is free text with the remembered `location` values
suggested.

**類別, 取得地點 and 車票類型 suggest as you type** (`components/Combobox.jsx`,
matching in `lib/suggest.js`). The list opens on focus and narrows with each
keystroke — prefix matches first, then anything containing the text — and ↑ /
↓ / Enter or a click picks. It is only a suggestion: Enter with nothing
highlighted keeps exactly what was typed, so a new value is as easy as a known
one. It replaced `<datalist>`, which only opened from its own triangle and drew
a native popup unlike anything else in the app; it renders into
`document.body` so the sheet's scroll box cannot clip it.

## 交通 (`/transport`)

`pages/Transport.jsx` is the 交通 nav item: **+ 新增路線** at the top, then
one card per route, the way `/trips` is one card per trip, under each route's
**群組**. Reads live under
`['transport-routes', ...]` (`index`, `detail`), and every write on either
page invalidates the whole prefix.

- **+ 新增路線** opens 起點 and 終點 fields and an optional 群組, which
  suggests the groups in use; 建立 is disabled until both places are
  filled and while a create is in flight, and a failure says
  無法建立路線，請再試一次。 Creating opens `/transport/{id}`.
- **Cards.** Each route is a card linking to `/transport/{id}`: 起點 → 終點,
  the first line of 備註, then one line per 交通方式 — the mode, 價錢 and 時間
  when set (`optionSummary` in `lib/transport.js`). A route with no options
  reads 沒有交通方式. Cards are in the route order the server keeps.
- **Groups.** Routes are shown grouped by `group_name` (`groupByName` in
  `lib/grouping.js`), the packing list's convention: a group's routes are
  adjacent and a group sits where its first route does — except that the
  ungrouped routes always come first, under no heading. Each named group has
  its name as a small heading.
- **Order.** A ⠿ grip to the left of each card drags it within its group
  (`Sortable.jsx`, as on the packing sheet; ↑ / ↓ on a focused grip moves it
  one place). The grip sits outside the card's link, so picking a card up
  never opens it. **排序群組**, shown once there are two named groups, orders
  the named groups in `GroupOrderDialog`. Either sends every route id in the
  new order — the ungrouped ones first (`orderAfterGroupSort`) — in one
  `PUT /api/transport-routes/order`; the cache takes the new order first
  (`reposition`), the response replaces it, and a refusal puts the server's
  order back with 排序沒有儲存，已還原。
- **Empty.** 還沒有路線。按「+ 新增路線」開始。

## 交通 detail (`/transport/:routeId`)

`pages/TransportRoute.jsx` is one route of the sheet's Transportation tab, in
full and editable. **← 交通** goes back to the index. A `/transport/{id}` that
answers 404 — or 422, for an id that is not a number — reads 找不到這條路線。

- **Header.** 起點 → 終點, each a cell, then **群組** (a cell suggesting the
  groups in use, （未分組） when empty — changing it moves the route to the
  end of the new group), then 備註. ⋯ 刪除路線 asks first, saying the options
  and departures go with it, and returns to `/transport`.
- **筆記.** Under 備註, a 筆記 section lists the route's notes
  (`note_entries`) in order: the title in bold when there is one, the
  description (a `TextAreaCell`, edited in place), then each link opening in a
  new tab, shown as its title when it has one and otherwise as host and path
  without the scheme (`noteLinkText`), cut short with an ellipsis on a narrow
  screen and titled with the full URL. With none
  it reads 還沒有筆記。 **+ 新增筆記** and each note's ✎ open the same form
  (`components/NoteEditor.jsx`, shared with 筆記): 標題, 說明 (an
  `AutoGrowTextarea`) and, per link, an optional 連結標題 and its URL, with
  ↑ / ↓ to move a link, ✕ to remove one and
  **+ 新增連結** to add another; the links save in the order shown. Empty link
  inputs are dropped before sending (`notePayload`), and 儲存 stays disabled —
  with 需要標題或至少一個連結。 under it — until there is a title or a link,
  since a description alone is refused (`canSaveNote`). It stays disabled too,
  with 有標題的連結需要網址。, while a link has a title and no URL, which saving
  would silently drop (`hasTitleWithoutUrl`). A failed save keeps
  the form open with 無法儲存筆記，請再試一次。 ⋯ 刪除筆記 asks first; a
  failed delete shows 無法刪除筆記，請再試一次。 Each note has a ⠿ grip; a drop
  sends every note id of the route in one
  `PUT /api/transport-routes/{id}/note-order`, the cache takes the order first,
  the route is read again afterwards, and a refusal shows
  排序沒有儲存，已還原。
- **Cells.** Each way of making the journey is a card. Every field on it is a
  cell with the sheet's rules: Enter or
  blur commits, Escape reverts, no Save button. 價錢 is a whole number shown as
  `NT$22`; anything else typed there is dropped rather than sent. The names
  that cannot be blank (交通方式, 起點, 終點) ignore an emptied cell and keep
  their value. 提前買票 is a toggle showing 需要 / 不需要. 路線圖, 時刻表 and
  即時動態 open in a new tab once set, and a ✎ beside each edits the URL.
- **Departures.** Two rows per card, 平日 then 假日, grouped client-side by
  `day_type` (`groupByDayType`) because the API reads holiday first. Inside a
  row the times fall under 早 / 中 / 下午 / 晚 (`groupByBucket`). An irregular
  time is a dashed chip titled 「不一定有這班」. The chip that
  `nextDeparture` picks for the current time is filled and followed by 下一班;
  the page's clock moves on once a minute. Today's day type and the time of
  day are read in Asia/Taipei (`Intl.DateTimeFormat`, as `lib/trips.js` does),
  not from the device clock, so a phone abroad still picks Taipei's next run.
- **Adding a time.** The input at the end of each row takes the sheet's
  notation, `*13:40` for an irregular one. Unparseable input shows 時間格式不對
  and sends nothing; a 409 shows 這班已經有了, rendered from the status, not
  from the API's `detail`.
- **Adding and deleting options.** + 新增交通方式 under the cards takes a mode.
  ⋯ on a card opens 刪除交通方式 behind a confirmation, which says the
  departures go with it. A chip's ✕ deletes one time without asking.
- **Order.** Each option card has a ⠿ grip before its 交通方式 and is dragged
  into order the way routes are on `/transport`. A drop sends every option id
  of the route in one `PUT /api/transport-routes/{id}/order`; the detail cache
  takes the new order first and the returned route replaces it, the index is
  refreshed for its one-line-per-option summary, and a refusal puts the
  server's order back with 排序沒有儲存，已還原。

## 行程 (`/trips`)

`pages/Trips.jsx` is the 行程 nav item: **+ 新增行程** at the top, then the
tabs. Reads live under `['trips', ...]` (`index`, `detail`); every write also
refreshes the packing-list queries, because a linked list's date comes from
its leg.

- **+ 新增行程** opens a name field, a 一般 / 範本 select and, when templates
  exist, a 從範本 select of every template, which fills the name. Choosing a
  template with a timed entry adds a required 出發日期, the Taipei day its
  earliest departure moves to (`needsStartDate`). 建立 is disabled until it is ready and while a create is in flight,
  and a failure says 無法建立行程，請再試一次。 Creating opens `/trips/{id}`;
  after a copy, a notice there names each source leg whose packing list was
  not carried
  (「台北車站 → 彰化火車站」在範本中連結了「台北去彰化」，請自行連結打包清單。),
  dismissed with 知道了. It travels in the navigation state, which 知道了
  clears, so Back and a reload do not bring a dismissed one back.
- **Cards.** Each trip is a card linking to `/trips/{id}`: its name,
  **已準備完成** or **未準備完成** and **已買票** or **未買票** (none for
  無需買票, and none at all on a 範本 — `readinessBadges`, as on the
  dashboard), a 狀態 badge on 一般 trips, then one line per entry in
  departure order — 起點 → 終點, the Taipei departure (抵達 and the arrival
  when only that is set), the duration when both are set and differ, and 車種
  when there is one (`legSummary` in `lib/trips.js`). A trip with no legs reads 沒有行程段. 保存
  and 自動保存 cards add the first line of 保存備註.
- **刪除模式** lives on the 自動保存 tab, where old trips pile up. It puts a
  checkbox on every card, with **全選** and **刪除所選（n）**, which is
  disabled with nothing ticked or while a delete is in flight. That opens one
  `ConfirmDialog` naming every selected trip and saying their legs go with them
  and a linked packing list is not affected; confirming calls
  `POST /api/trips/bulk-delete`. A failure shows 無法刪除，請再試一次。 完成
  leaves the mode and clears the selection.

## 行程 detail (`/trips/:tripId`)

`pages/Trip.jsx` is the sheet's This time tab: one trip, in full, entry by
entry — an entry is a leg in the API and 一段 on screen. **← 行程** goes back to
the index, on the tab the trip is on (`tabFor`). Nothing is listed below the
trip. A `/trips/{id}` that answers 404 — or 422, for an id that is not a
number — reads 找不到這個行程。

- **Header.** It is sticky: ← 行程, the name and ⋯, the controls, 備註 and
  保存備註 stay just below the nav bar on a canvas background with a rule
  under it while the entries scroll beneath. The page's `<main>` is
  `overflow-x-clip` rather than `overflow-x-hidden` for that reason — both
  stop a wide card scrolling the page sideways, but `hidden` makes `<main>` a
  scroll container, and a sticky header inside one never sticks to the
  viewport. The name is a cell that cannot be emptied, with a 範本, 保存 or
  自動保存 badge beside it. Under it `KindControls` — the 狀態 select on a
  一般 or 自動保存 trip, the 保存 checkbox and 當作範本, none of them on a 範本
  — then, except on a 範本, **已準備完成** and the ticket status, and on every
  trip the **單程 / 來回** toggle. A 範本 has **+ 從這份範本建立行程** there
  (`components/CreateFromTemplate.jsx`): a name, already filled from the
  template, and a 出發日期, required when some entry has a departure to move
  (`needsStartDate`), and 建立 makes a 一般 trip from it and opens it, with the
  same notice as 從範本 about packing lists the copy could not carry. Then the
  trip's overall 備註, one-way or round trip. The ⋯ menu
  holds 保存 (or 取消保存, which asks first, as the checkbox does), 當作範本
  and 刪除行程, which asks first and returns to `/trips`; a 範本's ⋯ offers
  only 刪除行程. **當作範本** creates a template of the same name with the
  entries on the same dates — the page sends the Taipei day of the earliest
  departure as `start_date`, or none when no entry has one (`firstDeparture`)
  — and opens it. On a saved or auto-saved trip, or whenever it has a remark,
  a **保存備註** cell sits under 備註. A change of 狀態 or kind keeps the page
  where it is. 過去使用 into a full 自動保存 opens `EvictDialog` once the
  index it names from has arrived fresh.
- **已準備完成** is a checkbox for the `done` flag, independent of 狀態 and
  kind. It can be ticked only when the trip is **ready** (`tripReadiness` in
  `lib/trips.js`, the server's rule): its tickets are not 未買票, and every
  entry has ticked every tick it shows — the booking code does not count.
  Until then it is disabled with what is missing beside it, （未買票）,
  （還有未完成的標籤） or both; unticking is always allowed. A 422 the server
  still returns shows 還沒準備完成：… under the controls. Any write that makes
  the trip not ready clears `done` on the server, and the refetch shows it.
- **The ticket status** is a three-way `Segmented` control: 未買票 / 無需買票 /
  已買票 (`ticket_status`).
- **單程 / 來回** (`round_trip`). A one-way trip is one list of entries under
  its 備註. A round trip keeps that overall 備註 (`notes`) in the header and
  shows two sections, **去程** and **回程**, each with a title cell
  (`outbound_title`, `return_title`), a remark (`outbound_notes`,
  `return_notes`), its entries and its own **+ 新增一段**, which sends that
  `section`. An entry with no section shows under 去程. Back to 單程 is refused
  while 回程 holds an entry, a title or a remark, and the screen says
  回程還有行程段、標題或備註。請先移到去程或刪除，再改回單程。 去程's title and
  remark are kept but not shown, and come back with the round trip.
- **Entries** are cards in `departs_at` order, an entry with no departure
  after every entry with one, then by id (`sortLegs`). The top line is
  起點 → 終點, each a cell; an emptied one keeps its value (`required` in
  `lib/cells.js`, as on 交通 and the trip's name), then the **類型** select and
  ⋯. Under it the times (`formatLegTimes`): the departure, the arrival (the
  clock alone when it is the same Taipei day, `formatArrival`) and the
  duration; the departure alone when that is all there is or the two are the
  same instant; `– {arrival}` with only an arrival; 未定時間 with neither. ✎
  opens two `datetime-local` inputs in Taipei time, both optional; choosing a
  departure while the arrival is empty fills the arrival with it
  (`fillArrival`), as the server does on save. A 422 shows
  抵達時間不能早於出發時間.
- **What a card shows follows its 類型**, from one table in
  `lib/legTypes.js` (`LEG_TYPES`), the same as
  `app/services/domain/leg_types.py`; `legTypes.test.js` and
  `tests/unit/test_leg_types.py` each pin theirs to the spec's table. The table
  names the type's fields, and for each tick and the booking code whether it
  is **fixed** (always shown, no toggle), **optional** (shown when the entry
  switches it on, starting at the type's default) or **absent**:

  | 類型 | fields | 已訂票 · 已付款 · 已取票 | code |
  | --- | --- | --- | --- |
  | 高鐵 | 車種 車號 座位 價錢 車票類型 方向 | fixed · fixed · fixed | fixed 訂票代碼 |
  | 火車, 客運 | 車種 車號 座位 價錢 車票類型 方向 | optional, on | optional on, 訂票代碼 |
  | 捷運 | 車種 價錢 方向 | absent | absent |
  | 公車 | 車種 車號 價錢 方向 | absent | absent |
  | 開車 | 乘車類型 車種 車號 座位 價錢 | 已訂 off · 已付款 off · absent | optional off, 訂單編號 |
  | 腳踏車 | 類型 | 已訂 off · 已付款 off · absent | optional off, 訂單編號 |
  | 走路 | — | absent | absent |
  | 飛機, 船, 其他 | 車種 車號 座位 價錢 車票類型 | optional, on | optional on, 訂票代碼 |

  已訂票 reads **已訂** and the code **訂單編號** on 開車 and 腳踏車
  (`flagLabel`). Changing the 類型 resets the flags to the new type's defaults
  on the server; values of fields the new type does not show are kept, only
  hidden.
- **Fields.** 車種, 車號, 座位, 方向, 價錢 (the shared `PriceCell`) and
  車票類型, with the remembered `ticket_type` values suggested, all commit like
  a cell. 乘車類型 on 開車 (叫車, 自駕自己的車, 租車) and 類型 on 腳踏車
  (自己的, YouBike, Moovo, 租車) are a select whose — stores null.
- **The booking code** (訂票代碼 / 訂單編號), when shown, is large and
  monospaced. Tapping copies it and shows 已複製 for two seconds; a refused
  clipboard shows 無法複製. ✎ edits it.
- **The ticks** the entry shows are toggles, each its own field.
- **⋯** holds 移到去程 or 移到回程 on a round trip (`PATCH section`), a
  顯示「…」 / 隱藏「…」 item for each optional tick and the code, and
  刪除這段, which asks first and says the entry's 備案 go with it.
- **備註** is a `TextAreaCell`.
- **Packing list.** A linked list shows as `打包清單：{name}`, a link to it; ✎
  opens a select of every list **except templates**, newest `created_at`
  first (`linkChoices` — this order is the picker's alone), each reading
  `{name} ({date}) · {created date, Taipei} · {status}` (`linkLabel`): the
  list's own 出發 date as `YYYY-MM-DD`, the way its header writes it, left out
  when it has none; then the 狀態 for a 一般 or 自動保存 list, 保存 for a saved
  one. A template the entry is already
  linked to stays in the list, so the select never reads （不連結） for a
  linked entry. （不連結） unlinks. A 409 shows 這份清單已經連到別的行程段. The
  list's own header then reads 由行程設定 for its date.
- **備案.** Under the packing list, set off by a rule down its left, an entry
  lists its backups in `departs_at` order, each a card labelled 備案 1, 備案 2…
  and otherwise the entry's own card: the same 類型, fields, times, ticks, code
  and 備註, edited the same way. It has no packing list, no 移到去程 / 移到回程
  and no 備案 of its own, and its ⋯ says 刪除備案. **設為主要**, first in a
  backup's ⋯, swaps it with the entry (`POST /api/trip-legs/{id}/promote`), with
  no confirmation because doing it again swaps back. **+ 新增備案** opens the same
  form as + 新增一段 (`POST /api/trip-legs/{id}/backups`), starting from the
  entry's 起點, 終點 and 出發時間 as they are when it opens; 類型 and 抵達時間 are
  left to choose. **A backup going between the same two places as its entry
  hides them** (`samePlaces`): the ✎ beside 備案 n opens them to edit and closes
  them again, and it is only there while they match. A backup's ticks count
  for nothing: `tripReadiness`, the date range, the calendar and the index's
  leg lines all read `trip.legs`, which does not include backups.
- **Adding.** **+ 新增一段** opens a form that asks for the **類型** first;
  only then does it show 起點 and 終點, two optional Taipei times (an empty
  arrival takes the departure as it is chosen), the type's fields, and a
  **顯示** checkbox for each optional tick and the code, starting at the
  type's default — fixed ones have none. 新增 is disabled until there is a type
  and both places. The booking code and 備註 are filled in on the card. A
  價錢 that is not a whole number says 價錢要是整數 and sends nothing.

## 筆記 (`/notes`)

`pages/Notes.jsx` is the 筆記 nav item: notes that belong to no trip or route,
read from `['notes']` (`GET /api/notes`).

- **+ 新增筆記** opens the note form from `components/NoteEditor.jsx`, the
  one a route's note uses, with two differences: a **title is required** —
  儲存 stays disabled with 需要標題。 until there is one — and there is a
  **群組** field suggesting the groups in use. Each note's ✎ opens the same
  form; changing 群組 moves the note to the end of the new group.
- **Groups.** Notes are shown grouped by `group_name` (`groupByName`), the
  ungrouped ones first with no heading, each named group under a small heading
  — the same convention as 交通's routes.
- **A note** reads as on a route: its title, its 說明 as a `TextAreaCell`
  edited in place, and its links, each opening in a new tab and shown by its
  title when it has one. ⋯ 刪除筆記 asks
  first; a failed delete shows 無法刪除筆記，請再試一次。
- **Order.** The ⠿ beside a note drags it within its group. Once there are two
  named groups, each heading has **↑ / ↓**, which move that group and its notes
  one place and save at once, with no dialog; the arrows that would pass either
  end are disabled, and all of them while a move is saving. The ungrouped notes
  have no heading and stay first. Either way every note id goes in the new
  order, the ungrouped first, in one `PUT /api/notes/order`; the cache takes it
  first, the list is read again afterwards, and a refusal shows
  排序沒有儲存，已還原。 Links are reordered in the form with ↑ / ↓.
- **Empty.** 還沒有筆記。按「+ 新增筆記」開始。

## 選項 (`/options`)

`pages/Options.jsx` holds the remembered values behind the 類別, 包包, 取得地點
and 車票類型 suggestions (see "Common options" in `business-rules.md`), with
one tab per kind: **類別（n）· 包包（n）· 取得地點（n）· 車票類型（n）**, in
`LABEL_KIND_LABELS` order, each counting its values (`optionCounts` in
`lib/options.js`). The tabs look like the index tabs and keep the tab the same
way, as `?tab=` — `bag`, `location` or `ticket_type`, and absent for 類別;
anything else reads as 類別 (`kindFromSearch`). The tab bar is written in the
page rather than reusing `IndexTabs`, whose tabs are the four kinds of list.

**The tab bar is sticky**, on a canvas background, so a long kind scrolls
under it and the other kinds stay one tap away. The sticky box is the outer
one, not the sideways scroller inside it: an `overflow-x-auto` box is a scroll
container, and a sticky element sticks only within its nearest one.

Each value is an input with its use count (用了 n 次). Edited, its button
becomes 改名; untouched, it is ✕, which removes the suggestion and leaves the
data alone. A rename shows how many rows it rewrote — 已改名，改寫了 n
筆資料。, or 已合併到「…」 when it lands on an existing value. A kind with no
values says 還沒有記下任何值。輸入過一次，它就會出現在這裡。

**備份到 Google Sheets** sits at the bottom of the page
(`components/BackupSection.jsx`): one 立即備份 button with no confirmation,
because a backup cannot lose data. While the request runs, the button reads
備份中… and is disabled. Success shows 已備份 with the Taipei time and the
number of rows written. A refusal shows this app's own sentence for each
status (`backupErrorMessage` in `lib/backup.js`): 409 another backup is
running, 422 the database is empty, 503 Sheets is unreachable or not set up.
The status code is shown faintly after the sentence, and the English `detail`
is never shown. Restore has no button here; the section says it is
`scripts/restore_sheet.py`. See `sheet-backup.md`.

## Mobile first

Checklist is the mobile view; the sheet scrolls horizontally. Build at 375px
and let it widen. Every button has a 44px minimum height, set globally in
`index.css` rather than per component — the kind of rule forgotten exactly
once, and then on the control that matters.

## The visual language is the media tracker's

Tailwind 4 through `@tailwindcss/vite`, with the token names and values copied
from `media/frontend/src/index.css`: bone paper, wisteria, flat surfaces, no
resting shadow, corners barely eased. Dark mode follows `data-theme` with the
OS preference as a fallback.

**The theme toggle** is the last thing in the nav bar: ☾ switches to dark, ☀
to light. The choice is stored in `localStorage` under `cg1618:theme`, the
media tracker's key and rule (`lib/theme.js`, tested beside it); with nothing
stored the page follows the OS, live. `index.html` applies the same rule in an
inline script before the first paint, so a dark phone never flashes bone paper
on load. Every colour comes from the semantic tokens, which is what lets one
attribute recolour every screen. Media-specific tokens, such as its per-media-type
scope hues, are not copied.

Use the semantic tokens (`bg-surface`, `text-text-muted`, `border-border`)
rather than raw colours, so a palette change reaches every screen at once.

## The 409 is a decision, not an error toast

The only `409` a kind change can meet is 過去使用 into a full 自動保存. On
`/lists`, on a list's own page and on a trip's page alike, it opens
`EvictDialog` — 這會刪除一份清單 (or 一個行程), the limit, and the names that
would go — with *save it instead* first, as the primary action (改為保存它);
confirming the delete (刪除並繼續) is second, and 取消 third. A destructive
confirm whose safe option is missing, or buried, gets clicked through.

Saving from that dialog saves what would go and **retries unconfirmed**, so the
retry succeeds because there is room rather than because it was forced. If the
save is refused, the dialog closes and nothing is retried; the refetch shows
what actually happened.
Confirming retries the same change with `evict_confirmed`.

The ids and names it needs come from `evict_next` on the index response — the
refusal's `detail` is a plain English string and is not shown. Nothing else
about a kind can be refused this way: creating is never limited, and 保存 and
取消保存 never are.

## Loading, error and empty

`src/components/States.jsx` defines all three once. Three screens disagreeing
about what "nothing here" looks like is how an app starts feeling like several.

An empty state offers the action that fills it. 「沒有範本」 is less useful
than 「按「當作範本」或新增一份範本，之後的新清單可以從它開始。」

## How the built bundle is served

**One process serves the API and the bundle, and nothing sits in front of it** —
cloudflared connects straight to uvicorn, so there is no proxy to serve a static
file this app declines to. `app/main.py` is the whole story:

- **`/assets/...`** is mounted as `StaticFiles`, when the build produced an
  `assets/` directory at all. Vite inlines every asset when the bundle is small
  enough, so the mount is conditional.
- **`/api/...`** is refused by the catch-all with a 404, even when
  unregistered. This app's health path is `/api/health`, so that one guard
  covers the deploy probe too; a mistyped endpoint must not come back as a 200
  carrying the bundle.
- **Any other path that names a real file inside the bundle is served as that
  file** — `favicon.svg`, `favicon.ico`, `robots.txt`, anything the build copies
  from `frontend/public/` to the root of `frontend_dist/`. The path is resolved
  and confined to the dist directory first, so `..%2F.env` cannot read a file
  beside the bundle.
- **Everything else is `index.html`**, so client-side routing works.

The order matters and is the same as `media`'s: the API routers are registered
before the catch-all, so it cannot shadow a route that exists.

**A file in `frontend/public/` reaches production only through this handler.**
Before it served real files, `/favicon.svg` answered with `index.html` under
`text/html` and the browser discarded it — the icon was in the repository and in
the bundle, and had never once been shown.

## The dev proxy uses 127.0.0.1

Not `localhost`. uvicorn binds IPv4 only, but Node resolves `localhost` to
`::1` first on Windows, and the proxy then fails with `ECONNREFUSED` against a
server that is plainly running. The media tracker found this the hard way and
its `vite.config.js` carries the same note.
