# Frontend

Last verified: 2026-09-30

**What this is for.** How the React app is laid out, where each kind of thing
lives, and the decisions a new screen has to follow. The endpoints it calls are
in `api.md`; the rules it renders are in `business-rules.md`.

## Layout

| Directory | What lives there |
| --- | --- |
| `src/api/` | `client.js` — the only place that calls `fetch()`. `endpoints.js` — every URL in one map. |
| `src/hooks/` | `useApiQuery.js` — TanStack Query over `fetchJson`, plus `useApiMutation` and `send`. `useLongPress.js` — a long-press that never also fires the click. |
| `src/pages/` | One file per screen, PascalCase, default export. |
| `src/components/` | `Grid` and `GridRow` (the sheet, and one row of it), `Checklist`, `Cell`, `RowMenu`, `ConfirmDialog`, `EvictDialog`, `States`. |
| `src/lib/` | Pure modules with no React in them. Tests sit beside them. |

Routes are declared in `src/App.jsx`. Every screen is editable, so every one of
them goes through TanStack Query — media's split is query hooks for anything
written back from the UI and plain `fetch` for read-only pages, and this app has
no read-only pages.

## The screen speaks the sheet's language

**Every string a person sees is Traditional Chinese**, in the owner's Google
Sheet's own words, except where the sheet itself is English: `Double Check`,
`Transportation`, `This time`, and the app's name `travel`. `index.html` says
`lang="zh-Hant-TW"`.

**Stored values stay English enum text** (`not_packed`, `night_before`,
`bring`). The mapping from a stored value to what the screen says lives in
**`src/lib/labels.js` and nowhere else** — a component that needs 已打包 imports
`STATUS_LABELS`, it does not spell it. `labels.test.js` walks every vocabulary,
so a value with no display string fails a test rather than rendering blank.

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

`lib/listHeader.js` builds both lines, pure so the day boundaries are tested:
`未設定日期`, `今天出發`, `明天出發`, `{n} 天後出發`, `已出發 {n} 天`, each
followed by the date; and progress as `已處理 {s} / {n}`, `{u} 項待確認`,
`可以出發了`. A list's own date is edited by clicking it. A date that comes from
a This time leg (`departure_source: "trip_leg"`) says so — `由 This time
行程設定` — and is not editable here, because it is changed on the leg.

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
已打包數量 is its own cell, as in the sheet, and turns amber when it is short
of 數量, because being short is the failure a packing list exists to catch.

Double Check is one select with three positions — 不需確認, 未確認, 確認 —
rather than two checkboxes. It maps onto `needs_double_check` and
`double_checked` (`CHECK_FIELDS` in `labels.js`). 需求 is a select whose empty
option (—) stores null; `SelectCell` treats `''` as null for any column that
may be unset. 取得地點 is free text with the remembered `location` values
suggested.

## Transportation

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
  the page's clock moves on once a minute.
- **Adding a time.** The input at the end of each row takes the sheet's
  notation, `*13:40` for an irregular one. Unparseable input shows 時間格式不對
  and sends nothing; a 409 shows 這班已經有了, rendered from the status, not
  from the API's `detail`.
- **Deleting.** ⋯ on a route or a card opens 刪除路線 / 刪除交通方式 behind a
  confirmation, which says the options and departures go with it. A chip's ✕
  deletes one time without asking.
- **Empty.** 還沒有路線。 with the add-route form; with routes present the same
  form sits at the bottom of the page.

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

`EvictDialog` names the list that would be destroyed and offers *save it
instead* first, as the primary action; confirming the delete is second. A
destructive confirm whose safe option is missing, or buried, gets clicked
through.

Saving from that dialog saves the list and **retries unconfirmed**, so the
retry succeeds because there is room rather than because it was forced.

The ids and names it needs come from `evict_next` on the index response — the
refusal's `detail` is a plain English string and is not shown. Un-saving (or
un-templating) a list can be refused the same way, because it moves the list
back under the cap; that refusal gets the same dialog in its own words, without
the save-instead option, and confirming retries the change with
`evict_confirmed`.

## Loading, error and empty

`src/components/States.jsx` defines all three once. Three screens disagreeing
about what "nothing here" looks like is how an app starts feeling like several.

An empty state offers the action that fills it. 「沒有範本」 is less useful
than 「在清單上勾選「範本」，之後的新清單可以從它開始。」

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
