# One `kind` and a `usage`, shared by lists and trips, instead of flags

Lists and trips share one model: a `kind` (`template` 範本, `saved` 保存,
`free` 一般), a `usage` that only a `free` row has, and `auto_saved_at`. 自動保存
is `kind = free AND usage = past`. The rules are in `business-rules.md`; this
is why.

- **Impossible combinations are unstorable.** Independent booleans (`saved`
  and `template` on a list, `archived` and `template` on a trip) allowed a
  saved template, an archived template, and states the screens had to
  reconcile. One `kind` column puts every row on exactly one shelf, and four
  check constraints keep `usage` and `auto_saved_at` consistent with it.
- **自動保存 is `free` + `past`, not a fourth kind.** "A 一般 row marked
  過去使用 is auto-saved" is then true by construction rather than kept in step
  by code, and leaving 過去使用 returns the row to 一般 with nothing else to
  undo.
- **One queue rule for two tables** (`app/services/domain/auto_save.py`),
  differing only in the limit and in a pair of lists sharing a slot.
- **Templates and saved rows are kinds of the same table**, edited on the same
  page, not a separate template table — a template *is* a list or a trip.
- **Templates are made by copying.** 當作範本 creates a new template from any
  list or trip rather than flipping the original, so a template's kind never
  changes and nothing becomes or stops being one by `PATCH`.
- **`usage` and saving are set by hand, are reversible, and lock nothing.**
  Moving a trip on automatically once its last leg ended, and a read-only
  saved state, were both considered and not wanted.
- **保存備註 (`archive_note`) is apart from `notes`**, because one is written
  before the trip and the other after.

**Why 自動保存 has a limit at all.** Lists are disposable; templates and saved
rows are kept. Without dropping old auto-saved rows, "copy a previous list"
degrades into a wall of forty names and stops being used — which would take the
most valuable feature with it. A row worth keeping is saved or made a template
explicitly, and a saved row is never offered for dropping.

Rejected:

- **Keep the booleans and add a status.** Every impossible combination
  survives, and a third column has to be kept consistent with two others.
- **A table per kind.** Moving a list to 保存 would be a copy between tables,
  its items and a leg's link with it, for what is a change of shelf.
- **A template table of its own**, which needs a second set of endpoints and
  screens for the same shape of data.
