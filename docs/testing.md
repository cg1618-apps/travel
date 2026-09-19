# Testing

Last verified: 2026-09-19

**What this is for.** How this application's tests are laid out, what each
fixture gives you, and the two rules that decide whether a test is worth
anything. Read it before writing a test that touches the database, and before
writing any test that asserts something is *refused*.

## Layout

| Directory | What lives there | Needs PostgreSQL |
| --- | --- | --- |
| `tests/` | Tests that need neither a schema nor a running app — configuration, the deploy hook's shape, the platform contract, SPA routing, the migration chain. | Only `test_migrations_build_the_schema.py`, which builds its own. |
| `tests/api/` | Everything that needs a schema or an HTTP client. | Yes. |
| `tests/unit/` | Tests with no database and no network. | No. |

Test files are named `test_<subject>.py`. Test functions are named as
sentences describing the behaviour — `test_a_nameless_item_is_a_422_not_a_500`,
not `test_create_item_invalid`. The name is what a failure prints, so it should
say what stopped being true.

## Running them

**One pytest at a time, across every repository on this machine.** All four
applications share one PostgreSQL, and concurrent runs produce
`relation does not exist` and unique-constraint failures that look like real
breakage. Take the machine-wide lock:

```bash
LOCK=/c/Users/cgent/AppData/Local/Temp/anime_site_pytest.lock
until mkdir "$LOCK" 2>/dev/null; do sleep 10; done
venv/Scripts/python.exe -m pytest tests/ -q; rc=$?
rmdir "$LOCK"; exit $rc
```

A lock directory older than 25 minutes is stale: `rmdir` it and say so.

## Fixtures

Defined in `tests/api/conftest.py`.

| Fixture | Scope | What it gives you |
| --- | --- | --- |
| `migrated_database` | session | A `travel_test` database built by `alembic upgrade head`, dropped at the end. |
| `engine` | session | An engine bound to it. |
| `db_session` | function | A `Session` inside a transaction that is rolled back on teardown, so no test sees another's rows. |
| `client` | function | A `TestClient` whose requests run inside that same transaction. |

`tests/conftest.py` holds `admin_url(database)`, which derives an
administrative connection URL from the app's own settings rather than
hardcoding a per-machine superuser password, and an autouse fixture that
reloads `app.config` after each test.

## The schema is built by the migrations

`migrated_database` runs `alembic upgrade head`. It does **not** call
`Base.metadata.create_all`, and that is a deliberate divergence from the media
tracker — see `notes/decisions.md`. A fixture built from the models tests the
models against themselves and proves nothing about the migrations, which is the
one place the drift is invisible.

`tests/api/test_the_fixture_runs_migrations.py` asserts this directly: it reads
`alembic_version`, which `create_all` never writes. If someone simplifies the
fixture back, that test is what goes red.

Two further claims are checked in `tests/test_migrations_build_the_schema.py`,
and they are not the same claim:

- **The chain builds from nothing** — `alembic upgrade head` run as a real
  subprocess against a scratch database created for the test. This is the
  from-zero proof.
- **An incremental upgrade succeeds** — a run against a database that already
  holds the earlier revisions. It proves the last step only.

Say which one you ran. The weaker claim stated honestly is worth more than the
stronger one rounded up.

## The frontend suite

**vitest**, configured in `frontend/vitest.config.js`, with tests **beside the
source they cover** — `src/lib/timing.test.js` next to `src/lib/timing.js` —
as the media tracker does it.

```bash
cd frontend && npm test          # once
cd frontend && npm run test:watch
```

It needs no lock and no database. CI runs it after the frontend lint.

What belongs here is logic with no server behind it, and the due-now
boundaries in `src/lib/timing.js` are the case that justified the runner: they
are a date comparison that is only wrong on the evening it matters. Both dates
are parameters rather than a `new Date()` inside the function, so a test can
stand on a boundary instead of waiting for one.

## A refusal test has to be able to fail

**Asserting that a gate allows is safe on an empty set; asserting that it
refuses is not.** A rule computing over a set — lists that count toward a cap,
items in a category, granted permissions — is vacuously satisfied when the set
is empty, and an empty set is exactly what a fresh test database gives you. A
refusal test can pass because there was nothing to refuse: green on day one,
green through the change that breaks it, green forever.

So every refusal test must make its set non-empty, and must say so. **A fixture
that exists to make a negative test bite is load-bearing and looks like
decoration** — `three_working_lists` in `tests/api/test_slots.py` is not scene
setting; it is the only reason the cap's refusal can fail.

Assert the mirror case with the same fixture. A green then proves the rule did
the refusing, rather than an empty table doing it for free.
