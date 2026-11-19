# A route's notes are `note_entries`, and their links are rows

A route already has `notes`, its 備註: one text column, carried by the importer
and the sheet. The titled notes with links are a separate list, and the
relationship and the API field are named `note_entries` so that neither the
code nor a caller can mistake one for the other. Rejected: renaming the old
column to make room, which means a migration, an importer change and a
sheet-format change for no gain.

**Links are a child table, `transport_note_link`** (and `note_link` for 筆記).
Rejected:

- **A PostgreSQL array.** It reads well in SQL, but the sheet backup writes one
  value per cell and restores by column type, and an array would be the first
  value needing its own encoding there.
- **A text column of newline-separated URLs**, which needs splitting and a rule
  for blank lines on every read.

A row per link costs one more table; in return each link is a plain row,
ordered by `position` like everything else ordered here, the backup handles it
with no new code, and a link's optional `title` is one nullable column. The API
still reads and writes a note's links as one ordered list and replaces the rows
wholesale: there is no per-link editing to justify per-link endpoints.

**A blank link is a 422, not dropped.** Dropping it silently would let a form
that sent an empty row believe it had saved one.
