# Frontend

Last verified: 2026-09-19

**What this is for.** How the React app is laid out, where each kind of thing
lives, and the decisions a new screen has to follow. The endpoints it calls are
in `api.md`; the rules it renders are in `business-rules.md`.

## Layout

| Directory | What lives there |
| --- | --- |
| `src/api/` | `client.js` — the only place that calls `fetch()`. `endpoints.js` — every URL in one map. |
| `src/hooks/` | `useApiQuery.js` — TanStack Query over `fetchJson`, plus `useApiMutation` and `send`. |
| `src/pages/` | One file per screen, PascalCase, default export. |
| `src/components/` | `Grid`, `Checklist`, `Cell`, `EvictDialog`, `States`. |
| `src/lib/` | Pure modules with no React in them. Tests sit beside them. |

Routes are declared in `src/App.jsx`. Every screen is editable, so every one of
them goes through TanStack Query — media's split is query hooks for anything
written back from the UI and plain `fetch` for read-only pages, and this app has
no read-only pages.

## Two views, and why there are exactly two

A packing list is used for two different jobs, and one screen cannot do both
well.

- **Sheet** (`components/Grid.jsx`) is where a list is *planned*. Every column
  is visible, every header sorts, every cell edits where it sits. It is what
  you would build in a spreadsheet, because that is what people do build.
- **Checklist** (`components/Checklist.jsx`) is where a list is *worked
  through*. A tick, a name, a quiet second line, one place to add, and finished
  things folded away. Nothing here is editable except the tick.

The switch names the two views. **It does not offer an axis to group by.** An
earlier version put "When / Category / Bag" on screen — internal vocabulary
from the data model, asked as a question of someone who wants to pack a bag.
Grouping is not a thing a person wants; seeing their list is. Sorting a column
covers the real need without asking anything.

The choice is remembered in `localStorage`, and a first visit on a narrow
screen starts on Checklist, because a sheet at 375px is a horizontal scrollbar.

## Spreadsheet conventions, because that is the reference

`components/Cell.jsx` implements the bargain every spreadsheet makes, so nobody
has to be told it:

- **Click a cell to edit it.** No pencil icon, no edit mode, no modal.
- **Enter or blur commits. Escape reverts.** Escape has to be safe — it is what
  people press when they realise they clicked the wrong cell.
- **There is no Save button** anywhere in the grid.
- **Every cell is one line.** A wrapping cell changes the row height and makes
  the sheet ripple while you type; the sheet scrolls sideways instead.

Quantity is one cell holding two numbers and a unit — "3 / 5 pairs" is one
fact, and three columns for it would widen the sheet for nothing. A short count
is marked, because being short is the failure a packing list exists to catch.

The double-check state is one control with three positions — off, needed, done
— rather than two checkboxes. It maps onto `needs_double_check` and
`double_checked`, and one thing to click makes *packed but not yet verified* a
state you can see rather than one you have to reason about.

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

The ids it needs come from `evict_next` on the index response — the refusal's
`detail` is a plain string and cannot carry them.

## Loading, error and empty

`src/components/States.jsx` defines all three once. Three screens disagreeing
about what "nothing here" looks like is how an app starts feeling like several.

An empty state offers the action that fills it. "No templates" is less useful
than "Tick *template* on a list to start future lists from it."

## The dev proxy uses 127.0.0.1

Not `localhost`. uvicorn binds IPv4 only, but Node resolves `localhost` to
`::1` first on Windows, and the proxy then fails with `ECONNREFUSED` against a
server that is plainly running. The media tracker found this the hard way and
its `vite.config.js` carries the same note.
