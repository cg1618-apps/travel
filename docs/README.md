# Documentation for travel

Start here. Every page describes the system **as it is**, in the present tense —
never how it got here. The record of how things changed lives in git history and
in `notes/`.

| Page | What it holds |
| --- | --- |
| `notes/decisions.md` | Why things are the way they are, including rejected alternatives. The one place that is allowed to talk about the past. |
| `superpowers/` | Where a spec and a plan live **while a task is in progress**, and nowhere else. Both are deleted when that task ends, with anything durable moved into a real page first — so the directory is absent between tasks, which is its normal state. |

There is no feature yet — no packing list, no buying list, no rules, no
transport information. What exists is the skeleton the features will sit on:
config read once from the environment, a `/api/health` endpoint that checks
the database's Alembic revision against the code's, an Alembic chain with one
baseline migration, a React/Vite frontend uvicorn serves once built, a
production container and compose file, and `dev.ps1` for local development.
Commands and ports are in `CLAUDE.md`, not repeated here. Pages appear as the
application does — a data model page when there is a schema, an API page when
there are endpoints.
