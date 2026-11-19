# The Travel sheet backup copies everything, and diverges from media's

The owner asked for one Google Sheet doing two jobs: restoring the database,
and being readable when the app is down — first in tiers (what the dashboard
shows, then all lists and trips, then everything). The tiers collapsed. Every
table copied whole costs less code than copying the dashboard's subset
correctly, which would have to follow leg → list links to stay consistent, and
a partial copy cannot be restored. So everything is backed up, and the
dashboard's subset became the *readable* tabs instead. How it works is in
`sheet-backup.md`.

- **Its own Google Cloud project and service account.** `cg1618` is meant for
  all of the platform's apps, one service account per app. The project holding
  media's key was made for the legacy anime site, and the owner chose not to
  grow it. One key per app also means a leaked or revoked key reaches one
  sheet.
- **Readable tabs are output only.** Restore reads only the per-table tabs, so
  the readable layout can change freely and never has to be parsed back.
- **The readable set adds legs' lists to the dashboard's rule**, because a trip
  in use whose return list is still 未使用 is the case where the app dying
  hurts. `交通` is readable too: transport is what is needed mid-trip.
- **`RAW`, not media's `USER_ENTERED`.** With `USER_ENTERED`, Sheets reparses
  every value: a `booking_code` `0123` would lose its zero and `TRUE` would
  become a boolean. Media escapes its date columns with `'` to avoid that; with
  `RAW` there is nothing to escape. The `總覽` links are the one `USER_ENTERED`
  write, because they are formulas.
- **One request, not media's SSE.** Media streams because a full backup of its
  52 tabs outlasts the tunnel's ~100-second idle limit. travel writes all its
  tabs in one batched call and one clear, finishes in seconds, and stays far
  below Sheets' per-minute write quota.
- **Refuse an empty database, not an emptied tab.** Media refuses a
  header-only write over any tab holding data. Here that would turn one
  legitimately empty table into a backup that refuses every night until
  someone clears the tab by hand. What media's guard is really about is a whole
  empty database, such as a fresh worktree's, wiping the sheet; travel refuses
  exactly that, before calling Google at all.
- **Restore replaces; media's Pull upserts.** An upsert cannot remove a row
  deleted since the backup, so media needs a separate Clean step. For one
  person's data, the backup is the whole truth.
- **Sequences move with `ALTER SEQUENCE ... RESTART`, not `setval`.** `setval`
  is not transactional, so a dry run or a failed restore would roll the rows
  back and leave the sequences moved.
- **Restore is a command, not a button** — the owner's choice. When the app is
  dead, a button cannot be pressed, and the one operation that deletes
  everything should take a deliberate command. A development-only button was
  offered and declined.
- **The nightly job resolves its checkout from its own path.** Media's `lib.sh`
  assumes `~/media`, which is the hazard the platform records about renaming
  media's checkout.
