# An item variant is a name plus a detail

`鑰匙` + `家鑰匙` and `鑰匙` + `宿舍鑰匙` are two ordinary rows sharing a
`name` and differing in `detail`, each packed on its own. The screen groups
them; the data stays flat, the way the owner's sheet is.

Rejected:

- **Parent and child items.** It adds a tree to a list that is a flat sheet,
  with its own ordering, deletion and check-off rules.
- **Folding the variant into the name** (`鑰匙 家鑰匙`). It cannot be grouped,
  cannot be shown the way the sheet shows it, and cannot be suggested.

How the screen groups them is in `frontend.md`, "Variants".
