# The stack is media's: FastAPI, PostgreSQL, React + Vite, Alembic

travel uses the media tracker's stack. The deciding factor was consistency
with an app that already works: its patterns can be copied rather than
reinvented, and someone moving between the two finds the same shape.

Rejected: Django, and a server-rendered frontend without a build step. The
cost of the chosen stack is known and accepted — a build step, a second port
in development, and a `frontend_dist/` that goes stale when nobody rebuilds.
