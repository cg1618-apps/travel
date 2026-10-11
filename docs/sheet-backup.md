# Backing up to the Travel sheet, and restoring from it

Last verified: 2026-10-07

**What this is for.** travel copies its whole database into a Google
spreadsheet called **Travel**. The copy serves two purposes:

- **restore**: rebuild every table from the sheet;
- **reading while the app is down**: the lists and trips in use, and all of
  transport, laid out the way the owner's original sheet was.

This is also how data moves between the home and company machines, and the
only copy of travel's data kept off the box. The box's own dumps are taken
only at deploy time and stay on the box.

Why it is shaped this way is in `notes/decisions.md`, "The sheet backup". The
endpoint is in `api.md`, the button in `frontend.md`, and the nightly job in
`deployment-selfhost.md`.

## Setup

- The spreadsheet belongs to the owner's Drive and is shared, as Editor, with
  the service account `travel@cg1618.iam.gserviceaccount.com`. That account
  lives in the Google Cloud project `cg1618`, which is meant for all of the
  platform's apps; the legacy project from the anime site is not used. Only
  the Sheets API is enabled, and the only scope requested is `spreadsheets`.
- **The sheet holds booking codes. Keep its General access on Restricted.**
- **Two sheets, one writer each.** A backup overwrites a whole sheet, so a
  development machine backing up into production's sheet would replace
  production's restore point with development data. The all-empty refusal
  cannot catch that, because a development database is rarely empty.
  - **Travel** is production's. Only the box writes it.
  - **Travel (dev)** is shared by the development machines, with the same
    service account.

  To bring production's data onto a development machine, restore with
  `--sheet-id <Travel's id>`.
- Two settings, in `.env` on every machine that backs up or restores
  (described in `.env.example`):
  - `GOOGLE_CREDENTIALS_JSON`: the service account's key, as **one line of
    compact JSON in single quotes**. The box's `bin/deploy` and
    `deploy/migrations` source `.env` with bash. A key written with spaces
    breaks into words that bash tries to run, and the deploy refuses before
    it starts. `.env.example` has the command that writes the line correctly
    without printing it.
  - `GOOGLE_SHEET_ID`: the id from the sheet's URL, between `/d/` and `/edit`.
    That is Travel on the box, and Travel (dev) everywhere else.

  If either is unset, the app still starts; a backup or restore answers that
  Sheets is not configured.

## What the sheet holds

The tabs, in the order the backup leaves them:

| Tab | For | What it holds |
| --- | --- | --- |
| `總覽` | reading | When the backup ran, and a link to each readable tab. |
| `清單 · <name>` | reading | One per list in the readable set (below). A header block with name, 狀態, 出發, 去程/回程, 備註 and 已處理 x / y, then one row per item in `position` order. |
| `行程 · <name>` | reading | One per trip in the readable set. A header block, then one row per leg in departure order, with Taipei times, booking state shown as ✓, the 訂票代碼 and the linked list's name. |
| `交通` | reading | Every route and option, with departures written as `06:10 *08:15`, where `*` marks an irregular departure. |
| `Backup Info` | restore | `backed_up_at`, the Alembic revision the database was at, and each table's row count. |
| `Label Option` … `Trip Leg` | restore | One tab per table, in restore order: every column, headed by its column name, and every row by `id`. |

**The readable set** is what the dashboard shows, plus one more rule:

- **Lists:** 一般 lists that are 使用中 or 未來使用, 使用中 first.
- **Trips:** 一般 trips that are 使用中 or 未來使用, 使用中 first.
- **Plus:** every list linked from a leg of one of those trips, whatever that
  list's own 狀態. A trip in use whose return list has not yet been set to
  使用中 is exactly the case where the app dying would hurt.

The rule lives in `app/services/domain/dashboard.py`. `tests/unit/test_dashboard_rule.py`
pins it to the same cases `kinds.test.js` uses for the frontend's
`onDashboard`.

Tab names are capped at 90 characters. A duplicate gets ` (2)`, ` (3)` and so
on, in `id` order.

**The backup owns its own tabs and no others.** Each run rewrites every tab it
writes, and deletes any `清單 ·` or `行程 ·` tab that has left the readable
set. A tab it does not recognise is left alone, moved after its own tabs. So
the owner can keep a tab of their own in the file. **Edits made in the backup's
own tabs are overwritten by the next backup.** The sheet is a copy, not a
second place to edit.

## Backing up

Three ways to run it, all doing the same thing:

- the 立即備份 button on the 選項 page (`POST /api/backup`);
- the nightly timer on the box, at 04:20 (`deploy/backup/`);
- by hand: `venv/Scripts/python.exe -m scripts.backup_sheet`.

What a run does, in order:

1. **It refuses an all-empty database before reading anything from Google.**
   An empty database is almost certainly the wrong one, such as a fresh
   worktree's. Backing one up is what wiped media's sheet on 2026-09-12. A
   single empty table is fine; that table's tab becomes header-only.
2. **It writes every tab in one batch, then trims what lies beyond the new
   data.** A failed write leaves the previous backup standing.
3. It links `總覽` to the tabs, deletes stale readable tabs, and puts the tabs
   in order. A failure here leaves a complete backup with an untidy front page,
   which the next run fixes.

All values are written `RAW`, so a booking code `0123` stays text and nothing
is reinterpreted in the sheet's locale. The `總覽` links are the only formulas.

**One backup runs at a time.** A PostgreSQL advisory lock (`1618_8002`)
spans the web app and the nightly process, and a second backup is refused
before it writes. Google's 429 and 5xx answers are retried. Once retries run
out, or when Google answers 403 or 404 (key revoked, sheet not shared, wrong
id), the backup reports Sheets as unavailable.

## Restoring

```bash
venv/Scripts/python.exe -m scripts.restore_sheet --dry-run
venv/Scripts/python.exe -m scripts.restore_sheet --replace
venv/Scripts/python.exe -m scripts.restore_sheet --sheet-id <id> --replace
```

**There is no button.** When the app is dead there is no page to press, and
replacing every table is the one operation here that destroys data. In
production it runs inside the container, by the manager session:
`docker compose -f docker-compose.prod.yml exec app python -m scripts.restore_sheet ...`.

**A restore replaces; it never merges.** Within one transaction it does three
things:

1. deletes every row of all eight tables;
2. inserts every row from the restore tabs with its original `id`;
3. moves each id sequence past the highest restored id, using
   `ALTER SEQUENCE ... RESTART` rather than `setval`, because `setval` would
   survive a rollback.

Everything is read and checked before the first delete. Any refusal or error
rolls back the whole transaction, and `--dry-run` rolls back on purpose after
printing the counts. Readable tabs are never read.

**It refuses, and writes nothing, when:**

| Condition | Why |
| --- | --- |
| `Backup Info` or a restore tab is missing | It is not a backup. |
| The sheet's Alembic revision is not the database's | The columns would not line up. Migrate first, or restore into a database at the sheet's revision. |
| The database holds rows and `--replace` was not passed | Every table's count is printed, so you see what would be deleted. |
| A tab's row count differs from `Backup Info`'s | The backup did not finish writing. |
| A header names no column, appears twice, or a non-null column has no header | Columns are matched by header name, never by position. |
| A cell cannot be stored in its column | The message names the tab, the row and the column. |

Restoring reads values back with these rules:

- A missing nullable column restores as null.
- A wholly blank row is skipped.
- **An empty cell is null**, in a text column too, so an empty string does
  not survive the round trip as `""`.

To move data to another machine:

1. On the machine that has the data, back up.
2. On the other machine, pull the same branch.
3. Run `alembic upgrade head`, so the database is at the same revision as the
   sheet.
4. Restore with `--replace`.

A development machine's own `GOOGLE_SHEET_ID` is Travel (dev). To restore
production's data instead, give Travel's id with `--sheet-id`.

## Tests

None of the tests talk to Google:

- An autouse fixture makes constructing a real gspread client fail, and
  `tests/unit/test_no_real_sheets_in_tests.py` proves the guard is armed.
- `tests/fake_sheets.py` keeps tabs in memory.
- The round trip in `tests/api/test_sheet_backup.py` seeds every table with
  edge values: a leading-zero booking code, a null count, an irregular
  departure, an unlinked leg, 自動保存 rows, and text that looks like a
  formula or a boolean. It backs up, wipes the database, restores, and
  compares every column of every row.
- Before restoring, that test moves each sequence back to the lowest id, so a
  restore that forgot the sequences would collide.

See `testing.md`.
