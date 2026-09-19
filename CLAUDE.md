# CLAUDE.md — travel

**The generic rules are not in this file.** Git workflow, branch and pull
request discipline, concurrent sessions, the machine-wide test lock, the
credentials rule, worktrees and documentation discipline live in
`cg1618-apps/platform`'s `CLAUDE.md`, one directory up. Claude Code loads it
first and this file second, so everything there applies here unless this says
otherwise.

## What this application is

**travel** is trip preparation, and the record of how to get places. What it is meant to
hold, in the owner's words:

- a **packing list** and a **buying list**;
- **rules** — the things learned the hard way and not to be relearned;
- **transportation information**, both general and for the trip currently
  planned.

**This is deliberately the smallest of the four applications**, media included.
That makes it the best candidate to take through the deploy pipeline first: the
smallest surface on which to prove the platform's app contract end to end.

## Status

**Nothing is built.** There is no stack, no schema, no application code. The
next step is design, not implementation — brainstorm into
`docs/superpowers/specs/`, and only then plan.

## The contract this app owes the platform

Four things, none of which names a framework:

1. **A container listening on port 8002**, publishing nothing to the host.
2. **A health path** that answers 200 only when the app can actually serve —
   not a route that returns 200 with the database down. It is declared in the
   platform's `apps.yml` as `/health`; change it there if this app exposes
   something else.
3. **`DATABASE_URL` read from the environment.**
4. **A `main` branch that is production**, moving only by pull request.

The platform's `docs/registry.md` and `docs/shared-stack.md` hold the detail,
including the network alias (`travel-app`) the tunnel routes to.

## Stack

**FastAPI + PostgreSQL on the backend, React + Vite on the frontend** — the
same shape as the media tracker, deliberately. Four months of patterns exist to
copy from, and the platform's app contract is enforced by `apps.yml` and the
deploy pipeline rather than by every app being different.

The cost is known and accepted: a build step, a second port in development, and
a `frontend_dist/` that goes stale if you forget to rebuild. The media
tracker's `CLAUDE.md` documents each of those.

Migrations: Alembic, which means this app ships `deploy/migrations` with
`current`, `added` and `downgrade` once it has a schema — the hook the
platform's rollback calls. See the platform's Step 4 plan.

## Who can see it

**Nobody but you, today.** `exposure: cloudflare-access` in the platform's
registry: Cloudflare authenticates before a request reaches the box, so there
is no login page, no session, no password and no auth code in this app. One
user, one person's data.

**But sharing is expected**, and the shape is already known: a single trip's
information sent to the people going on it. That is why this app is *not* on
the platform's never-public list — for `journal`, `health` and `money` public
is never correct; here it is a change the app is meant to want.

Three things make that change cheap, and all three are free now and expensive
later:

1. **Anything shareable lives under `/s/...`** from the first route. Opening one
   trip to the world is then an Access policy that exempts that prefix, not a
   redesign — because Access is all-or-nothing per path.
2. **Shareable entities carry a visibility field from the first migration** —
   `private` / `unlisted` / `public`, everything `private`. The column is
   trivial to add later; retrofitting the *checks* at every read path is not.
3. **A password on a shared thing is a share token, not an account.** There is
   never a second identity here, so the model is "this trip has a secret link,
   optionally with a passphrase" — a field on the object, never a users table.

**The dangerous moment is the flip**, if it ever comes: moving from
`cloudflare-access` to `public` moves the gate from Cloudflare into this
codebase. The visibility checks have to work *before* that lands, and be tested
for refusal with fixtures that make refusal possible — a check over an empty set
passes without ever firing.

## Commands

```bash
venv/Scripts/python.exe -m pytest tests/ -q      # tests
venv/Scripts/ruff.exe check .                    # lint
cd frontend && npm run build                     # writes frontend_dist/ for uvicorn
cd frontend && npm run lint                       # oxlint
alembic upgrade head
alembic revision --autogenerate -m "describe change"

.\dev.ps1   # shared Postgres (anime_site_postgres_db, database "travel") +
            # uvicorn --reload on :8002 + vite on :5175, one window
```

**Ports are box-wide**, allocated in the platform's `apps.yml`: uvicorn binds
the app's registry port, and Vite binds `5173 + (port - 8000)`. `travel` is
uvicorn `8002`, Vite `5175` — `media`'s `8000`/`5173` on the same laptop must
stay undisturbed, which is why `dev.ps1` refuses to start rather than picking
a free port when 8002 is already held.

**One PostgreSQL container, one database per app.** `travel` has no
`docker-compose.yml` of its own in development — it runs its `travel`
database inside `anime_site_postgres_db`, the same container `media` starts,
created once by the platform's provisioning. `dev.ps1` starts that container
if it is stopped; it never creates or owns it.
