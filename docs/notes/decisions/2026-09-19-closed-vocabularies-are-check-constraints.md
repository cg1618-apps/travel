# Closed vocabularies are text plus a CHECK; open ones are free text

A column whose values are a small closed set that the application branches
over exhaustively — `status`, `timing`, `leg`, `visibility`, `kind`, `need`,
`transport_type` and the like — carries a `CheckConstraint`. A value outside
the set is a bug, not a new option. This follows media's *discriminator*
precedent (`ck_movies_media_type`) rather than its open-vocabulary one, where
values live in a constants module with no constraint because the list grows.

A column whose values grow with use — `category`, `bag`, `location`,
`ticket_type` — is free text, suggested by `label_option` and constrained by
nothing. `need` (closed) beside `location` (open) on the same item is the
clearest pair: one is a question the code answers by branching, the other is
wherever something happens to be got.

**Text plus a constraint, not PostgreSQL `ENUM` types.** Adding a member to a
PG enum inside a reversible revision is disproportionate ceremony. The
constraint is generated from the `StrEnum` in `app/constants.py`, so the two
cannot drift. A nullable closed column spells its null arm out, because
`x IN (...)` is NULL rather than TRUE for a null value.
