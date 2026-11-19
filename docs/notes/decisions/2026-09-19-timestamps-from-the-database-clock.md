# Timestamps come from the database clock

**A divergence from media**, which defaults timestamps in Python from a
Taipei-now helper. Here `created_at` and `updated_at` are
`server_default=now()` on `timestamptz` columns.

The database clock is correct for a row written by a migration, by the
importer or by hand in `psql` as well as by the app, and needs no helper. Where
a timestamp is shown — the leg picker shows a list's created date — the client
converts it to Asia/Taipei, so the zone of the clock that wrote it does not
matter.
