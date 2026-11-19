# A plain integer primary key, not media's UUID plus public id

**A divergence from media**, which gives every row a UUID `system_id` and a
sequence-backed `public_id`. That pair exists there to give Google Sheets round
trips a stable key and users a short one.

travel exposes no ids to anybody, and its sheet backup needs no stable key: a
restore *replaces* every table with the ids it backed up rather than merging
into existing rows (`sheet-backup.md`). So a second key would be a column with
no reader, and a UUID a wider index with no benefit. If sharing ever needs an
unguessable identifier, it belongs on the share token, not on every row.
