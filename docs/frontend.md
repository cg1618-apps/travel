# Frontend

Last verified: 2026-09-19

**What this is for.** How the React app is laid out, where each kind of thing
lives, and the handful of decisions a new screen has to follow. The endpoints
it calls are in `api.md`; the rules it renders are in `business-rules.md`.

## Layout

| Directory | What lives there |
| --- | --- |
| `src/api/` | `client.js` — the only place that calls `fetch()`. `endpoints.js` — every URL in one map. |
| `src/hooks/` | `useApiQuery.js` — TanStack Query over `fetchJson`, plus `useApiMutation` and `send`. |
| `src/pages/` | One file per screen, PascalCase, default export. |
| `src/components/` | Shared pieces: `ItemRow`, `ItemEditor`, `EvictDialog`, `States`. |
| `src/lib/` | Pure modules with no React in them. Tests sit beside them. |

Routes are declared in `src/App.jsx`. Every screen here is editable, so every
one of them goes through TanStack Query — the media tracker's split is query
hooks for anything written back from the UI and plain `fetch` for read-only
pages, and this app has no read-only pages.

## The visual language is the media tracker's

Tailwind 4 through `@tailwindcss/vite`, with the token names and values copied
from `media/frontend/src/index.css`: bone paper, wisteria, flat surfaces, no
resting shadow, corners barely eased. Dark mode follows `data-theme` with the
OS preference as a fallback. What is **not** copied is anything media-specific,
such as its per-media-type scope hues.

The point is that someone moving between the four apps should recognise the
product. Use the semantic tokens (`bg-surface`, `text-text-muted`,
`border-border`) rather than raw colours, so a palette change reaches every
screen at once.

## Mobile first

This app is used standing over an open suitcase holding a phone. Build at
375px and let it widen; `max-w-2xl` and a 16px gutter is the whole layout.

Every button has a 44px minimum height, set globally in `index.css` rather than
per component — it is the kind of rule that gets forgotten exactly once and
then only on the control that matters.

**The item row is the status control.** Tapping anywhere on it cycles
`not_packed → packed → no_need`, so working down a list is one thumb and no
aiming. The double-check and edit affordances are separate targets on the same
row.

## Two things that are deliberately not automatic

**The 409 is a decision, not an error toast.** `EvictDialog` names the list
that would be destroyed and offers *save it instead* first, as the primary
action; confirming the delete is second. A destructive confirm whose safe
option is missing, or buried, gets clicked through.

Saving from that dialog saves the list and **retries unconfirmed**, so the
retry succeeds because there is room rather than because it was forced.

**Due-now is computed here, not on the server**, in `src/lib/timing.js`,
because the viewer's calendar day is the one that matters. Both dates are
parameters so the boundaries can be tested — see `testing.md`.

## Loading, error and empty

`src/components/States.jsx` defines all three once. Use them rather than
writing a spinner per page: three screens disagreeing about what "nothing here"
looks like is how an app starts feeling like several.

An empty state offers the action that fills it. "No templates" is less useful
than "No templates. Mark a list as a template to start from it next time."

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
