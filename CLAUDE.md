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

**Undecided, and deliberately so.** Python and PostgreSQL are the only things
guaranteed across this box; the web framework, whether there is a frontend at
all, and the migration tool belong to this application.

Record the decision in `docs/notes/decisions.md` when it is made, with what was
rejected and why — and update this section, the CI workflow and
`requirements-dev.txt` in the same change.

## Commands

```bash
venv/Scripts/python.exe -m pytest -q      # tests
venv/Scripts/ruff.exe check .             # lint
```

That is all there is until a stack is chosen. Add commands here as they become
real, not before.
