# Deployment, and getting back from a bad one

Last verified: 2026-09-19

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

There is one revision in this app that creates anything: **`p1acking0001`**,
which creates `packing_list`, `packing_item` and `label_option`. Downgrading
past it **drops all three tables and everything in them** — every list, every
item, every remembered option.

So for a release that carried `p1acking0001`:

| Option | What it costs |
| --- | --- |
| Let `bin/rollback` downgrade | Every packing list on the box, gone. |
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

If it answers `0001_baseline`, the packing tables do not exist yet and a
downgrade costs nothing — that revision is deliberately empty. If it answers
`p1acking0001` or later, the tables exist and the table above applies.

**This page deliberately does not record what production is at.** That is a
fact this repository cannot keep true, and an app file holding a platform fact
it cannot keep true is how `CLAUDE.md` came to claim this app was `status:
planned` for a day after it went live.

## The shared database is shared

`travel` has no database of its own on the box. It uses the platform's
PostgreSQL, one database per app.

**Use `docker compose stop db`, never `docker compose down`.** Every tree is
in one compose project — which is exactly what `COMPOSE_PROJECT_NAME` pinning
is *for*, since it makes a worktree mount the real volume instead of silently
creating an empty one — and the same project name makes the *container* shared
too. A `down` in any tree removes the container all four apps are using. It
happened on the development machine on 2026-09-19; no data was lost, because
`down` without `-v` leaves named volumes alone, but on the box it would take
production's database out from under four apps with nobody in front of it.

## Why there is one page here and two in `media`

`media` splits this across `deploy/README.md` and
`docs/deployment-selfhost.md`. This app is the smallest of the four and has one
migration; a second page would be a second place to go stale. If `deploy/`
grows past the single hook, split it then.
