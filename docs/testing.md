# Testing

Last verified: 2026-11-18

**What this is for.** How this application's tests are laid out, what each
fixture gives you, and the two rules that decide whether a test is worth
anything. Read it before writing a test that touches the database, and before
writing any test that asserts something is *refused*.

## Layout

| Directory | What lives there | Needs PostgreSQL |
| --- | --- | --- |
| `tests/` | Tests that need neither a schema nor a running app — configuration, the deploy hook's shape, the platform contract, SPA routing, the health probe with its reads stubbed. | No. |
| `tests/unit/` | Tests with no database and no network. | No. |
| `tests/api/` | Everything that needs a schema, an HTTP client or a database of its own — the routers, the backup and import, the migration chain and the release round trip. | Yes. |

**The split between the two tiers is the directory, and nothing else.**
Everything outside `tests/api/` is the *unit tier*: it never opens a
connection, so it runs with no PostgreSQL at all (`pytest tests
--ignore=tests/api`), and a pull request into `dev` runs it on every change. A
test that needs the database goes in `tests/api/`; a test outside it that
starts needing one is in the wrong place. No marker is involved, because a
marker forgotten on one test silently moves it to the wrong tier and a
directory cannot be forgotten.

Test files are named `test_<subject>.py`. Test functions are named as
sentences describing the behaviour — `test_a_nameless_item_is_a_422_not_a_500`,
not `test_create_item_invalid`. The name is what a failure prints, so it should
say what stopped being true.

## Running them

**Every run has a database of its own**, so two runs never collide through
this app's tests: the database is named for the run, not fixed (see "The
run's database" below). The machine-wide lock is still taken, because the
platform's rule is that it stays until all four apps meet that standard —
one app on a fixed name breaks the guarantee, and a session cannot tell from
outside which have switched:

```bash
LOCK=/c/Users/$USERNAME/AppData/Local/Temp/anime_site_pytest.lock
until mkdir "$LOCK" 2>/dev/null; do sleep 10; done
venv/Scripts/python.exe -m pytest tests/ -q; rc=$?
rmdir "$LOCK"; exit $rc
```

A lock directory older than 25 minutes is stale: `rmdir` it and say so.

## Fixtures

Defined in `tests/api/conftest.py`.

| Fixture | Scope | What it gives you |
| --- | --- | --- |
| `migrated_database` | session | The URL of this run's own database, built by `alembic upgrade head` and dropped `WITH (FORCE)` at the end. |
| `scratch_database` | function | The name of an empty database for one test that builds its own chain, dropped afterwards. |
| `engine` | session | An engine bound to it. |
| `db_session` | function | A `Session` inside a transaction that is rolled back on teardown, so no test sees another's rows. |
| `client` | function | A `TestClient` whose requests run inside that same transaction. |

`tests/sheet_fixture.py` builds, in memory, a small workbook shaped like the
owner's sheet — the four tabs with their real headers, one ignored tab, and
rows carrying the sheet's quirks: inherited blank cells, an item named `無`,
float numbers, a day-fraction time, `*` and `...` departure cells, a route with
no end and one with no mode. The parser and writer tests share it, so no
`.xlsx` is ever committed.

`tests/conftest.py` holds an autouse fixture that reloads `app.config` after
each test, and the revision helpers the health tests read.

### The run's database

`tests/databases.py` mints every database a test touches, and nothing else
creates one. Names are `travel_test_<epoch>_<hex>` — never a fixed name, and
never read from `.env`; only the server and the credentials come from the
app's own settings (`server_url`), so the tests work wherever the app does.
It is the media tracker's `tests/databases.py`, and the platform's
`docs/registry.md`, "How an app's tests use the shared server", is the rule
it implements.

- **The run's database** is created and migrated by `migrated_database` the
  first time a test needs it, and dropped `WITH (FORCE)` when the session
  ends, so an assertion that leaves a connection open cannot block the drop.
- **Every scratch database** — the from-zero build, the revision tests, the
  round trip — comes from the same `scratch()` helper under the same kind of
  name. A scratch database with a fixed name collides with itself exactly as
  the main one did.
- **Leftovers are swept once per run**, before the run creates anything
  (`_leftovers_swept`): a `travel_test_*` database with no connections that is
  older than two hours is dropped. A database with a connection belongs to a
  run in progress. A *young* one with none may be a run between
  `CREATE DATABASE` and its first connection, which is why the epoch is in
  the name. So a crashed run's database is gone by the first run two hours
  later.
- **Every test connection goes to `127.0.0.1`**, even when a machine's `.env`
  names `localhost`. Windows resolves `localhost` to `::1` first, the
  development database listens on the IPv4 loopback only, and each new
  connection — every `alembic` subprocess, every engine — waited 21 seconds
  before falling back. The app's own default host is `127.0.0.1` for the same
  reason.
- `drop()` refuses any name it did not mint, so no mistake here can drop
  `travel` or another app's database.

`tests/api/test_test_databases.py` pins all of that against a real server,
with the in-use and the young database as the mirrors of the swept one.

**No test writes outside `tmp_path`, and none creates a cluster-wide
object** — no role, no tablespace, no database outside `tests/databases.py`.
A fixed file path is a fixed database name by another route.

**No test reaches Google.** `_no_real_google_sheets`, an autouse fixture in
`tests/conftest.py`, makes constructing a `gspread.Client` raise. The guard is
needed because the developer's `.env` holds the real key and the real sheet
id, and a backup from the near-empty test database would overwrite the only
off-box copy of travel's data. The block sits at gspread itself, so no helper
path gets round it. `tests/unit/test_no_real_sheets_in_tests.py` proves it is
armed, since deleting the fixture would otherwise break nothing visible. It
patches by hand rather than through `monkeypatch`: as an autouse fixture,
`monkeypatch`'s undo would run after `restore_config_defaults` reloads the
config.

`tests/fake_sheets.py` is the in-memory spreadsheet the backup and restore
tests hand to `SheetClient`. It imitates the API's real shapes, and the code
depends on each of them:

- it refuses a write outside a tab's grid;
- it drops trailing empty cells and rows when read;
- it omits `values` for an empty range.

It also records each call, so a test can assert what was *not* done.

## The schema is built by the migrations

`migrated_database` runs `alembic upgrade head`. It does **not** call
`Base.metadata.create_all`, and that is a deliberate divergence from the media
tracker — see `notes/decisions.md`. A fixture built from the models tests the
models against themselves and proves nothing about the migrations, which is the
one place the drift is invisible.

`tests/api/test_the_fixture_runs_migrations.py` asserts this directly: it reads
`alembic_version`, which `create_all` never writes. If someone simplifies the
fixture back, that test is what goes red.

`tests/api/test_migrations_build_the_schema.py` checks six further claims:

- **The chain builds from nothing** — `alembic upgrade head` run as a real
  subprocess against a scratch database created for the test, then read back
  for the head revision and every table the models declare. This is the
  from-zero proof.
- **There is exactly one head** — `alembic heads` prints one line, and it is
  the revision nothing else names as its parent. Two branches that each add a
  revision on the same parent merge cleanly in git and fail here.
- **The chain downgrades to base and back** — upgrade head, `downgrade base`,
  upgrade head again, on a scratch database. Before the downgrade it inserts a
  `location` and a `ticket_type` label option: the downgrades that narrow
  `ck_label_option_kind` delete those rows first, and on an empty database that
  step would meet nothing and a downgrade missing it would still pass. The
  seeded rows are what make it bite.
- **`k1ind0000001` maps every flag combination, and back** — on a scratch
  database at `t3rip0000003`, one list and one trip per combination of the old
  booleans is seeded, the revision applied, every row's `kind` and `usage`
  checked, then downgraded and the booleans checked again (a saved-and-template
  row comes back a template only). Without the seed the `UPDATE`s meet nothing
  and a wrong `CASE` would still pass.
- **`p3acking0003` turns a `0` count into no value, and back** — from
  `k1ind0000001`, one item with `quantity_packed` 0 and one with 3 are seeded;
  after the upgrade the 0 is null and the 3 untouched, and an insert naming no
  count stores null. The downgrade fills the nulls with 0 and the column is
  NOT NULL again. Unseeded, both `UPDATE`s would meet nothing.
- **`t5rip0000005` backfills, and refuses to invent a time** — from the
  revision before it, one trip and one timed leg are seeded; after the
  upgrade both carry the backfilled defaults. An untimed leg then makes the
  downgrade refuse with "will not invent a time", and the mirror — the same
  downgrade with that leg deleted — goes through.

**A revision test finds the revision before its own through Alembic's
`ScriptDirectory`** (`previous("k1ind0000001")`), never by writing the
parent's id in. Reparenting a revision to fix two heads changes its parent,
and a test holding the old id would then exercise the wrong step without
failing. A revision-specific test is written in the branch that adds its
revision and kept until that revision is deployed (the platform's
`docs/registry.md`, "Migration tests: what is permanent and what is
retired"); the from-zero build, the one head and the round trip stay for
good.

### The release round trip

`tests/api/test_migration_round_trip.py` downgrades a scratch database from
head to **the revision `origin/main` is at** — what a rollback of the release
does — upgrades it again, and compares every sequence, constraint, index and
column with the snapshot taken before the downgrade. Exit codes alone would
pass a pair that runs cleanly and lands somewhere else.

`origin/main`'s revision is found from git and Alembic together: `git
ls-tree origin/main alembic/versions/` lists the revision files `main` holds,
and the walk goes down from head through Alembic's `ScriptDirectory` until it
reaches a revision whose file is among them. When this checkout holds no
revision beyond `main`, the range is one step (`-1`); when `origin/main`
cannot be read at all — a shallow clone, a checkout never fetched — it falls
back to one step too, and says so with a warning. CI checks out with
`fetch-depth: 0`, which brings `origin/main`, so CI always checks the whole
release. `test_the_release_range_is_what_a_rollback_would_undo` pins the walk
on a made-up chain with no database and no git.

None of those is the same claim as **an incremental upgrade succeeds** — a run
against a database that already holds the earlier revisions, such as the
development database. That proves the last step only.

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

What belongs here is logic with no server behind it, and date boundaries are
the case that justifies the runner: a date comparison is only wrong on the
evening it matters. `daysUntil` in `src/lib/timing.js` takes both dates as
parameters rather than calling `new Date()` inside, and `dayTypeOf` and
`nextDeparture` in `src/lib/departures.js` take the instant, so a test can
stand on a boundary instead of waiting for one.

**A test of Taipei time must not depend on the machine's zone.** The
departures and trips helpers read the weekday and the clock in Asia/Taipei, so
their tests pass UTC instants whose Taipei time is known —
`2026-09-26T00:00:00Z` is Saturday 08:00 in Taipei — and include one on each
side of a Taipei midnight that is not a UTC one. A test written with a local
`new Date(2026, 8, 26, 8, 0)` passes on a machine set to Taipei and fails
everywhere else.

## A refusal test has to be able to fail

**Asserting that a gate allows is safe on an empty set; asserting that it
refuses is not.** A rule computing over a set — slots in a full queue,
items in a category, granted permissions — is vacuously satisfied when the set
is empty, and an empty set is exactly what a fresh test database gives you. A
refusal test can pass because there was nothing to refuse: green on day one,
green through the change that breaks it, green forever.

So every refusal test must make its set non-empty, and must say so. **A fixture
that exists to make a negative test bite is load-bearing and looks like
decoration** — `full_lists` and `full_trips` in `tests/api/test_auto_save.py`
are not scene setting: five auto-saved list slots and ten auto-saved trips are
the only reason 自動保存's refusal can fail, and
`test_past_under_the_limit_is_not_refused` is the mirror on the same rows.

Assert the mirror case with the same fixture. A green then proves the rule did
the refusing, rather than an empty table doing it for free.

The same holds for a rule that **leaves something alone**. Each of these has a
row in its fixture that exists only so the test can fail, marked
`Load-bearing` in a comment:

- `test_a_reset_unpacks_clears_counts_and_checks_but_leaves_no_need_alone`
  holds a `no_need` item; without one it cannot tell "left alone" from "never
  there".
- `test_after_id_does_not_move_another_lists_items` gives the other list
  items past position 0, so a shift that leaked across lists would show.
- `test_an_import_refuses_when_any_target_exists_and_writes_nothing` seeds one
  route and nothing else, so the refusal has to come from the route check.
- `test_a_linked_list_takes_the_taipei_date_of_its_leg` departs at 00:30
  Taipei, which is the previous day in UTC; a daytime departure is the same
  date in both zones and would pass with the zone read wrong.

Two more of the same shape arrived with the logging contract, and both are
easy to read as decoration:

- **`test_the_f_string_guard_can_actually_fail`.** Its neighbour,
  `test_no_log_call_formats_its_own_message`, walks `app/` with an AST scan and
  asserts it found nothing. A detector that matches nothing at all passes that
  identically, and would keep passing through the change that fills this app
  with f-string log calls. This one feeds the detector a known-bad module and
  proves it fires.
- **`test_an_id_of_exactly_sixty_four_characters_is_honoured`.** Every
  rejection case in `tests/unit/test_request_id.py` asserts "a fresh id was
  generated instead" — which a validator refusing *everything* would also
  satisfy. This is the acceptance, and it sits on the boundary rather than
  safely inside it, so an off-by-one in the pattern is caught too.

And one that is weaker than it looks unless read closely:
`test_uvicorns_own_loggers_are_taken_over` asserts the handler **by identity**
against the root console handler. Asserting that *some* handler exists passes
while the bug is present, because uvicorn installs one of its own — which is
the entire failure being guarded against.

## What CI runs

`.github/workflows/ci.yml` (workflow name `Tests`) runs on every pull request
and in the merge queue (`merge_group`), and on nothing else, on
`ubuntu-latest`. Its one job is `test`, the check the repository ruleset
requires on `main` and `dev`. It checks out the whole history — every branch,
so `origin/main` is there for the release round trip — and decides whether
the change touches anything but documentation. Only if it does does it go on.

Every code change then gets the **fast checks**: the deploy and backup
scripts are executable in the commit, exactly one Alembic head, `ruff check
.`, shellcheck, `npm ci`, the frontend lint, the frontend tests and the
frontend build. How much of the backend suite runs depends on the trigger,
as the platform's `docs/registry.md`, "What runs when", lays out:

| Trigger | Backend tests |
| --- | --- |
| pull request into `dev` | the unit tier (`tests/unit` and every test file directly under `tests/`), plus every test file the pull request adds or edits |
| …that touches `alembic/` or `app/models/` | the above, plus the from-zero build with its revision tests (`test_migrations_build_the_schema.py`), the release round trip, and every file in `tests/api/` that names, in quotes, a revision the pull request adds or edits |
| …that touches the test harness (`tests/conftest.py`, `tests/databases.py`, `tests/api/conftest.py`), `requirements*.txt`, `alembic.ini`, `alembic/env.py`, `ci.yml` or `scripts/pr_tests.py`, or whose diff is empty | the full suite, because a change there can break any test without touching it |
| `merge_group` (the merge queue into `dev`) | the full suite |
| pull request into `main` (the release) | the full suite |

The selection for a pull request into `dev` is `scripts/pr_tests.py <base>
<head>`, which prints pytest's arguments one per line, or `FULL`. It is the
same script, in the same shape, as `media`'s and `food`'s, so all the apps
select tests the same way. The decision itself is a pure function, and
`tests/unit/test_pr_tests.py` pins it with no git and no database —
including the mirror that a database test naming some *other* revision is
not picked. To see what a branch would run:

```bash
venv/Scripts/python.exe scripts/pr_tests.py origin/dev HEAD
```

**The lighter pull-request run is only safe because of the merge queue.** A
pull request into `dev` is tested in full in the queue, on `dev` plus
everything queued ahead of it, and lands only if that passes. The test step
prints the selection it ran (or `FULL`), so the log says which way it went.
The `postgres:17` service is declared on every run, since a service cannot
depend on a step's output.

### A documentation-only pull request skips the job

The job's first step after the checkout diffs the pull request against its base
(`git diff --name-only <base>...<head>`, with the checkout at `fetch-depth: 0`
so the base is present). When every changed path is under `docs/` or ends in
`.md` — `README.md` and `CLAUDE.md` included, wherever they sit — every other
step is skipped, and `test` reports passed within seconds. One changed file of
any other kind runs the whole job, and so does an empty diff: the fast path is
taken only on positive evidence that nothing but documentation moved.

The run's log says which way it went: the deciding step prints every changed
path, and on the fast path its last line is `Documentation only: every other
step is skipped.`, with each later step marked skipped.

**It is a step condition, not a workflow-level `paths-ignore`.** A workflow
that does not run reports nothing, and a required check that is never reported
leaves the pull request blocked for ever. Skipping the steps inside a job that
does run reports `test` as passed, which is what the ruleset waits for.

The `postgres:17` service still starts, because a service cannot depend on a
step's output; that is most of the few seconds a documentation-only run takes.
Nothing in the suites reads a file under `docs/` or a Markdown file, which is
what makes skipping them sound — a test that starts to would have to be
covered by narrowing the rule.
