# travel

Packing and buying lists, transport information, and the current trip.

One of the applications on the [cg1618 platform](https://github.com/cg1618-apps/platform).
It is registered in that repository's `apps.yml`, which assigns it
`travel.cg1618.com`, port 8002 and the database `travel`.

**The skeleton is built; there are no features yet.** FastAPI serves the API
and the built React bundle from one process, Alembic owns the schema, and
`/api/health` answers 200 only when the revision the database is stamped with
matches the head the running code ships. There is no packing list, no trip, no
rules and no transport information — and no tables for them.

`main` is production and moves only by a release pull request from `dev`.
