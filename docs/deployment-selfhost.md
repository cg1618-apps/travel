# Deployment, and getting back from a bad one

Last verified: 2026-10-01

**What this is for.** What a release of `travel` does to the box, and what your
options are when one fails. `bin/rollback` names this page when it freezes, so
it is written to be read under pressure: **the section that matters is [When
the rollback freezes](#when-the-rollback-freezes)** and it is near the top for
that reason.

The platform owns the pipeline and documents it in `cg1618-apps/platform`
(`docs/registry.md`, `docs/shared-stack.md`). This page holds only what is
specific to this app.

## What a release does

`main` moves by pull request, the reusable workflow builds the image, and
`bin/deploy` puts it on the box. Two things then happen that matter here:

1. **`entrypoint.sh` runs `alembic upgrade head` on every container start.**
   The schema is brought up by the app itself, not by a separate step.
2. **`/api/health` answers 200 only when the revision the database is stamped
   with matches the head the running image ships.** A half-applied deploy
   fails this even though pages still serve, which is the whole point of it.

`deploy/migrations` is the hook the platform calls. It has three subcommands —
`current`, `added` and `downgrade` — and it must be committed executable
(`git ls-tree HEAD -- deploy/migrations` must show `100755`; CI asserts it).

## When the rollback freezes

`bin/rollback` exits **3** and stops. It has already told you the pre-deploy
dump, the git revision the code was at, and the revision the schema was at.

**Read this before restoring anything.**

### `bin/rollback` never restores data

It reverses *schema*, through this app's own migration hook, and swaps the
image back. That is deliberate and it is in the script's own header: undoing a
dropped column recreates it empty, so a migration that dropped data leaves that
data only in the dump.

### For `travel`, reversing the schema destroys data

Every revision after `0001_baseline` creates something, and downgrading past
it **drops what it created and everything in it**. In chain order:

| Revision | Downgrading past it drops |
| --- | --- |
| `p1acking0001` | `packing_list`, `packing_item` and `label_option` — every list, every item, every remembered option. |
| `p2acking0002` | Each item's `detail`, `need` and `location`, and every remembered `location` option. |
| `t1ransport01` | `transport_route`, `transport_option` and `transport_departure` — the whole Transportation page. |
| `t1rip0000001` | `trip` and `trip_leg` — every trip and booking, and every remembered `ticket_type` option. The packing lists they linked survive. |
| `t2rip0000002` | Each trip's `visibility`. Nothing reads it yet, so nothing visible is lost. |
| `t3rip0000003` | Each trip's `archived`, `archive_note` and `template` — every archive remark is lost, and archived trips and templates come back as ordinary trips. |
| `k1ind0000001` | Every list's and trip's `kind`, `usage` and `auto_saved_at`, and every list's `notes` and `archive_note` — usage statuses and list remarks are lost. A saved list or trip comes back saved (a trip archived), a template comes back a template, and one that was both saved or archived and a template before the upgrade comes back a template only. |

So for a release that carried any of them:

| Option | What it costs |
| --- | --- |
| Let `bin/rollback` downgrade | Whatever the table above says for every revision the release added. |
| Restore the pre-deploy dump | The dump was taken **before** the release, so every write made since is gone. |
| Fix forward | Nothing, if you can ship a fix. |

**There is no route that keeps the data.** The dump is not a gentler path — it
is a different loss, and usually a larger one, because a failed deploy normally
did not touch data at all while restoring definitely does.

**So the default is fix forward.** Roll the schema back only when the app
cannot serve at all and a fix is not minutes away.

### Working out what you would actually lose

Ask the database rather than assuming. From the box:

```bash
docker compose -f ~/cg1618/docker-compose.prod.yml exec -T db \
    psql -U postgres -d travel -tAc \
    "SELECT version_num FROM alembic_version"
```

If it answers `0001_baseline`, nothing exists yet and a downgrade costs
nothing — that revision is deliberately empty. Anything later has created the
tables named above up to and including that revision, and a downgrade to the
revision the rollback targets drops each one past it.

**This page deliberately does not record what production is at.** That is a
fact this repository cannot keep true, and an app file holding a platform fact
it cannot keep true is how `CLAUDE.md` came to claim this app was `status:
planned` for a day after it went live.

## The shared database is shared

`travel` has no database of its own on the box. It uses the platform's
PostgreSQL, one database per app.

**On the box, use `docker compose stop db`, never `docker compose down`.** A
`down` removes the container all four apps are using, and there that is
production's database taken out from under four apps with nobody in front of
it. `down` without `-v` leaves the named volume alone, so it is recoverable —
but it is an outage nobody asked for.

**On a development machine this is no longer a trap**, and the paragraph that
used to be here described one that has been removed. The development database
lived in `media`'s compose project, so a `down` in any media tree took it from
every other app; that happened on 2026-09-19 and read as data loss for ninety
seconds. It is now the platform's own project — `docker-compose.dev-db.yml`,
container `cg1618-dev-db`, volume `cg1618_dev_pgdata` — so nothing an app runs
can adopt or destroy it.

## Why there is one page here and two in `media`

`media` splits this across `deploy/README.md` and
`docs/deployment-selfhost.md`. This app is the smallest of the four and has one
migration hook; a second page would be a second place to go stale. If `deploy/`
grows past the single hook, split it then.
