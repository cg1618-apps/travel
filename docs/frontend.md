# Frontend

Last verified: 2026-10-01

**What this is for.** How the React app is laid out, where each kind of thing
lives, and the decisions a new screen has to follow. The endpoints it calls are
in `api.md`; the rules it renders are in `business-rules.md`.

## Layout

| Directory | What lives there |
| --- | --- |
| `src/api/` | `client.js` — the only place that calls `fetch()`. `endpoints.js` — every URL in one map. |
| `src/hooks/` | `useApiQuery.js` — TanStack Query over `fetchJson`, plus `useApiMutation` and `send`. `useLongPress.js` — a long-press that never also fires the click. |
| `src/pages/` | One file per screen, PascalCase, default export. |
| `src/components/` | `Grid` and `GridRow` (the sheet, and one row of it), `Checklist`, `Cell`, `PriceCell`, `RowMenu`, `ConfirmDialog`, `EvictDialog`, `KindControls`, `States`. |
| `src/lib/` | Pure modules with no React in them. Tests sit beside them. |

Routes are declared in `src/App.jsx`: `/` the dashboard, `/lists` and
`/lists/:listId` the packing lists, `/transport` 交通, `/trip` and
`/trips/:tripId` 行程, `/trips/auto-saved` 自動保存的行程 (declared above
`/trips/:tripId`, which would otherwise read it as an id), `/options` 選項.
Any other path renders the dashboard.
The nav bar names the last four; the app's name `travel` links to `/`. Every screen is editable, so every one of
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
limits shown as `n / 5` and `n / 10`, every row of an index once — are pure
helpers in `lib/kinds.js`, tested beside it.

**An API `detail` is never rendered.** It is English by contract (`api.md`).
`ErrorState` says 發生錯誤。 with the status code; `EvictDialog` writes its own
body and takes the names from `evict_next`.

## Two views, and why there are exactly two

A packing list is used for two different jobs, and one screen cannot do both
well.

- **表格, the sheet** (`components/Grid.jsx`) is where a list is *planned*. Every column
  is visible, every header sorts, every cell edits where it sits. It is what
  you would build in a spreadsheet, because that is what people do build.
- **清單, the checklist** (`components/Checklist.jsx`) is where a list is
  *worked through*. A tick, a name, a quiet second line, one place to add, and
  finished things folded away under 已完成. Nothing is edited in place; the
  tick and the row menu are all it offers.

The switch names the two views. **It does not offer an axis to group by.** An
earlier version put "When / Category / Bag" on screen — internal vocabulary
from the data model, asked as a question of someone who wants to pack a bag.
Grouping is not a thing a person wants; seeing their list is. Sorting a column
covers the real need without asking anything.

The choice is remembered in `localStorage`, and a first visit on a narrow
screen starts on Checklist, because a sheet at 375px is a horizontal scrollbar.

## The dashboard

`/` (`pages/Dashboard.jsx`) shows what is in use now and edits nothing. It
reads the indexes the other screens already own — `['packing-lists']` and
`['trips', 'index']` — so a write anywhere refreshes it.

- **清單** — 一般 lists that are 使用中 or 未來使用 (`onDashboard` in
  `lib/kinds.js`), 使用中 first, each with its 狀態 badge. Each row links to the
  list and shows its 出發 (`departureLabel` in `lib/timing.js`, shared with
  the index) and `已處理 {settled} / {items}`. 所有清單 links to `/lists`.
- **行程** — 一般 trips that are 使用中 or 未來使用, the same way, each with its
  狀態 badge and its date range or 沒有行程段, linking to `/trips/{id}`.
  前往行程 links to `/trip`.
- **Nothing else, and nothing to add.** 自動保存, 保存 and 範本, and every
  create form, belong to `/lists` and `/trip`; the dashboard only links there.
  An empty section says so plainly (目前沒有使用中或未來使用的清單。 /
  目前沒有使用中或未來使用的行程。) and offers nothing.

## 打包清單 (`/lists`)

`pages/PackingLists.jsx` puts every list on one of four shelves, in this order,
as sections rather than tabs because there are rarely more than a handful:

- **一般** — each row has `KindControls`: a 狀態 select, a 保存 checkbox and a
  當作範本 button.
- **自動保存** with its count, `n / 5` — the same row; 狀態 reads 過去使用,
  and changing it returns the list to 一般. The first line of 保存備註 sits
  under the name.
- **保存** — the 保存 checkbox and 當作範本, and the first line of 保存備註.
- **範本** — no controls: a template's kind never changes and it has no 狀態.

Each empty shelf says how a list gets there. **+ 新增清單** opens a form with
名稱, 出發日期, 類型 (一般 or 範本) and 從哪份清單複製項目, which offers every
list once, any kind, with its badge.

**當作範本** creates `{name}（範本）` with the items copied and shows a notice
linking to it, dismissed with 知道了. **Unticking 保存** asks first, in
`KindControls` itself so every place that shows the checkbox asks the same
question: 取消保存後會回到一般清單（未使用）。 **過去使用 into a full 自動保存**
opens `EvictDialog` (see "The 409 is a decision").

## The sheet's columns

In the sheet's order: **類別 · 項目 · 數量 · 已打包數量 · 打包狀態 · Double
Check · 打包時機 · 需求 · 取得地點 · 備註**, then a ⋯ column for the row menu.
項目 spans two cells: the name, and its `detail` beside it.

**`bag` is not shown.** The sheet has no such column. The field stays in the
data and in the copy rule, and its remembered values are still managed on the
選項 screen; nothing on the sheet reads or writes it.

## Variants: split rows, grouped on screen

Every row is its own item. `鑰匙 · 家鑰匙` and `鑰匙 · 宿舍鑰匙` are two items
sharing a name, each with its own status.

Under the list's own order (no column sorted), rows come from `groupRuns` in
`lib/grouping.js`: 類別 is written only on the first row of a run of equal
categories and 項目 only on the first row of a run of equal names, the cells
beneath left blank — how the Google Sheet reads. A row continuing a name run
has a lighter top border, so an item and its variants read as one block. A
blank cell is still a cell: clicking it opens the editor on the value the row
really holds.

**Sorting by any column turns grouping off** and every row shows its full
name; a blank cell under a foreign order would be ambiguous. Clearing the sort
(a third click on the header) brings the grouping back.

**新增變化** in the row menu inserts a new item directly below the row,
carrying its `category` and `name` (`after_id` on item create — see `api.md`).
Grouping then blanks both, so the variant appears in place, waiting for its
`detail`.

The checklist groups the same runs with `groupForChecklist`: a group of one is
a single line (`name · detail`); a group of several is the name as a heading
with each variant indented beneath it, each with its own tick. 未打包 items and
finished ones are grouped separately, so a group can appear in both halves.
The quiet second line is 需求, 取得地點, `已打包 {packed} / {quantity}{unit}`
and 備註, joined with ` · `; an outstanding Double Check adds a 待確認 link that
marks it confirmed.

## 打包狀態: three stored, two tapped

All three values stay in the data — 不需打包 is a decision, and folding it into
未打包 would make it indistinguishable from forgetting. But a tap only ever
means *packed*:

- **One tap** — the 打包狀態 pill in the sheet, the tick in the checklist —
  toggles 未打包 ⇄ 已打包 (`tapStatus` in `lib/status.js`). A 不需打包 row, shown
  greyed and struck through, returns to 未打包 on one tap.
- **不需打包 is one step further**: a long-press (500 ms) on the pill or the
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

## 重設狀態

A button in the list header, behind a `ConfirmDialog`. It calls
`POST /api/packing-lists/{id}/reset`: 已打包 → 未打包, 已打包數量 → 0, Double
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
the new template. Then a **備註** cell, and a **保存備註** cell when the list is
saved or auto-saved or already has a remark. 過去使用 into a full 自動保存
opens the same `EvictDialog`; the index it names from is fetched only once a
refusal has happened, and 改為保存它 appears when it has arrived.

## Spreadsheet conventions, because that is the reference

`components/Cell.jsx` implements the bargain every spreadsheet makes, so nobody
has to be told it:

- **Click a cell to edit it.** No pencil icon, no edit mode, no modal.
- **Enter or blur commits. Escape reverts.** Escape has to be safe — it is what
  people press when they realise they clicked the wrong cell.
- **There is no Save button** anywhere in the grid.
- **Every cell is one line.** A wrapping cell changes the row height and makes
  the sheet ripple while you type; the sheet scrolls sideways instead.

數量 is one cell holding the target and its unit — "5 雙" is one fact.
The number must be whole: anything else (`1.5`, `兩`) reverts the cell and
sends nothing, unit included, the way 價錢 refuses a typo; an emptied number
clears it. 已打包數量 refuses the same way, and an emptied one is 0. All three
cells read their text with `parseWholeNumber` in `lib/numbers.js`.
已打包數量 is its own cell, as in the sheet, and turns amber when it is short
of 數量, because being short is the failure a packing list exists to catch.

Double Check is one select with three positions — 不需確認, 未確認, 確認 —
rather than two checkboxes. It maps onto `needs_double_check` and
`double_checked` (`CHECK_FIELDS` in `labels.js`). 需求 is a select whose empty
option (—) stores null; `SelectCell` treats `''` as null for any column that
may be unset. 取得地點 is free text with the remembered `location` values
suggested.

## 交通

`/transport` is the sheet's Transportation tab as an editable page
(`pages/Transport.jsx`, one query, `['transport-routes']`, invalidated by every
write). Each route is a section headed 起點 → 終點; each way of making the
journey is a card under it.

- **Cells.** Every field on a card is a cell with the sheet's rules: Enter or
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
- **Deleting.** ⋯ on a route or a card opens 刪除路線 / 刪除交通方式 behind a
  confirmation, which says the options and departures go with it. A chip's ✕
  deletes one time without asking.
- **Empty.** 還沒有路線。 with the add-route form; with routes present the same
  form sits at the bottom of the page.

## 行程

`/trip` is the sheet's This time tab (`pages/Trip.jsx`): the current trip, leg
by leg. `/trips/:tripId` shows any other trip through the same component. Reads
live under `['trips', ...]` (`current`, `detail`, `index`); every write also
refreshes the packing-list queries, because a linked list's date comes from
its leg.

- **No trip.** `/api/trips/current` answers 404, which the page treats as an
  answer rather than an error: 目前沒有使用中或未來使用的行程。 with the
  new-trip form, and the sections below it so every other trip stays
  reachable. A new trip is 未使用 (or a 範本), never current, so it opens at
  `/trips/{id}`. A `/trips/{id}` that answers 404 reads 找不到這個行程。
- **Header.** The name is a cell that cannot be emptied, with a 範本, 保存 or
  自動保存 badge beside it. Under it `KindControls` — the 狀態 select on a
  一般 or 自動保存 trip, the 保存 checkbox and 當作範本, none of them on a 範本
  — then 備註. The ⋯ menu holds 保存 (or 取消保存, which asks first, as the
  checkbox does), 當作範本 and 刪除行程, which asks first; a 範本's ⋯ offers
  only 刪除行程. **當作範本** creates `{name}（範本）` with the legs on the
  same dates — the page sends the source's own first Taipei day as
  `start_date` — and opens it. On a saved or auto-saved trip, or whenever it
  has a remark, a **保存備註** cell sits under 備註.
- **Leaving current.** On `/trip`, 保存 or any change of 狀態
  (`leavesCurrent` in `lib/kinds.js`) moves the page to `/trips/{id}` rather
  than letting the trip vanish under the click — 使用中 → 未來使用 included,
  since another 使用中 trip would then take `/trip` over. 過去使用 into a full
  自動保存 opens `EvictDialog`.
- **Legs** are cards in `departs_at` order. The top line is 起點 → 終點, each
  a cell; an emptied one keeps its value (`required` in `lib/cells.js`, as on
  交通 and the trip's name). Under it the departure, the arrival
  (the clock alone when it is the same Taipei day, `formatArrival`) and the
  duration. ✎ opens two `datetime-local` inputs
  in Taipei time; a 422 shows 抵達時間要晚於出發時間.
- **Fields.** 車種, 車號, 座位, 價錢 (the shared `PriceCell`) and 車票類型,
  with the remembered `ticket_type` values suggested, all commit like a cell.
- **訂票代碼** is large and monospaced. Tapping copies it and shows 已複製 for
  two seconds; a refused clipboard shows 無法複製. ✎ edits it.
- **已訂票 / 付款 / 取票** are three toggles, each its own field.
- **Packing list.** A linked list shows as `打包清單：{name}`, a link to it; ✎
  opens a select of every list (all four shelves, each once) and
  （不連結）. A 409 shows 這份清單已經連到別的行程段. The list's own header then
  reads 由行程設定 for its date.
- **Adding and deleting.** + 新增一段 takes the places and two Taipei times;
  ⋯ 刪除這段 asks first.
- **Below the trip**, every other trip — the trip on screen is left out of
  every section — each row linking to the trip with its date range
  (`tripDateRange`):
  - **一般** — 一般 trips not 過去使用, each with its 狀態 badge.
  - **保存** — saved trips, each with the first line of its 保存備註.
  - **範本** — templates.
  - then a link, **自動保存的行程（n / 10）→**, always shown.
- **+ 新增行程** sits in the 一般 heading on a trip's page and is the only way
  to a second trip, because once any trip is current `/trip` shows one rather
  than the empty state. It opens a name field, a 一般 / 範本 select and, when
  templates exist, a 從範本 select of every template. Choosing a template with
  legs adds a required 出發日期, the Taipei day its first leg moves to.
  Creating goes to `/trips/{id}`; after a copy, a notice names each source leg
  whose packing list was not carried
  (「台北車站 → 彰化火車站」在範本中連結了「台北去彰化」，請自行連結打包清單。),
  dismissed with 知道了. It travels in the navigation state, which 知道了
  clears, so Back and a reload do not bring a dismissed one back. With no
  current trip the empty state offers the same form. A section with nothing to
  list is omitted, except 一般 on a trip's page, which holds + 新增行程.

## 自動保存的行程

`/trips/auto-saved` (`pages/AutoSavedTrips.jsx`) lists every auto-saved trip,
newest first, with its date range and the first line of its 保存備註, under a
heading counting `n / 10`. It is reached from the link below the trip on the
行程 page, and from nowhere in the nav bar; ← 行程 goes back.

**刪除模式** is here because this is where old trips pile up. It puts a
checkbox on every row, with **全選** and **刪除所選（n）**, which is disabled
with nothing ticked or while a delete is in flight. That opens one
`ConfirmDialog` naming every selected trip and saying their legs go with them
and a linked packing list is not affected; confirming calls
`POST /api/trips/bulk-delete`. A failure shows 無法刪除，請再試一次。 完成 leaves
the mode and clears the selection. With nothing auto-saved the page says how a
trip gets there, and offers no 刪除模式.

## Mobile first

Checklist is the mobile view; the sheet scrolls horizontally. Build at 375px
and let it widen. Every button has a 44px minimum height, set globally in
`index.css` rather than per component — the kind of rule forgotten exactly
once, and then on the control that matters.

## The visual language is the media tracker's

Tailwind 4 through `@tailwindcss/vite`, with the token names and values copied
from `media/frontend/src/index.css`: bone paper, wisteria, flat surfaces, no
resting shadow, corners barely eased. Dark mode follows `data-theme` with the
OS preference as a fallback. Media-specific tokens, such as its per-media-type
scope hues, are not copied.

Use the semantic tokens (`bg-surface`, `text-text-muted`, `border-border`)
rather than raw colours, so a palette change reaches every screen at once.

## The 409 is a decision, not an error toast

The only `409` a kind change can meet is 過去使用 into a full 自動保存. On
`/lists`, on a list's own page and on the 行程 page alike, it opens
`EvictDialog` — 這會刪除一份清單 (or 一個行程), the limit, and the names that
would go — with *save it instead* first, as the primary action (改為保存它);
confirming the delete (刪除並繼續) is second, and 取消 third. A destructive
confirm whose safe option is missing, or buried, gets clicked through.

Saving from that dialog saves what would go and **retries unconfirmed**, so the
retry succeeds because there is room rather than because it was forced.
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
