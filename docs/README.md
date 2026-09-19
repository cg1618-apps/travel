# Documentation for travel

Start here. Every page describes the system **as it is**, in the present tense —
never how it got here. The record of how things changed lives in git history and
in `notes/`.

| Page | What it holds |
| --- | --- |
| `notes/decisions.md` | Why things are the way they are, including rejected alternatives. The one place that is allowed to talk about the past. |
| `api.md` | Every HTTP endpoint, the shared conventions, and the two-step refusal that guards the cap. |
| `frontend.md` | How the React app is laid out, the visual language it shares with the media tracker, and the mobile-first rules a new screen follows. |
| `business-rules.md` | What fills the three-list cap, what a copy carries, when an item is due, and how the common options behave. |
| `data-model.md` | Every table, what each column means, and which rules the database itself enforces. |
| `testing.md` | How the tests are laid out, what each fixture gives you, and what a refusal test has to set up before it can fail. |
| `superpowers/` | Where a spec and a plan live **while a task is in progress**, and nowhere else. Both are deleted when that task ends, with anything durable moved into a real page first — so the directory is absent between tasks, which is its normal state. |

Packing lists are built. There is still no trip, no buying list, no rules and
no transport information. Under the feature sits the skeleton:
config read once from the environment, a `/api/health` endpoint that checks
the database's Alembic revision against the code's, the Alembic chain, a
React/Vite frontend uvicorn serves once built, a production container and
compose file, and `dev.ps1` for local development. Commands and ports are in
`CLAUDE.md`, not repeated here. Pages appear as the application does, so this
table grows with it.
