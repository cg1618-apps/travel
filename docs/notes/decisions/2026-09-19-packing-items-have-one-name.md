# Packing lists and items carry one `name`, not `name_cn` / `name_en` / `aliases`

The platform-wide naming convention, shared with `food` and `art`, is
`name_cn`, `name_en` and `aliases[]`, with `name_cn` as the display default.
Packing lists and items deviate: they carry a single `name`.

The convention exists for library entities that other people's data flows
into — an ingredient, a film, an artist. A packing item is a line typed at
midnight, and a second language field plus an aliases array on each one has no
reader. If a shared trip ever needs to be read in the other language, that is
a property of the share rather than of every row.
