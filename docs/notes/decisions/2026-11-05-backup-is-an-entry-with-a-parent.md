# A backup (備案) is an entry with a parent, and `Trip.legs` leaves it out

A backup holds everything an entry holds — a backup flight has a type, times,
a seat and a booking code as much as the first choice does — so the owner
chose a full entry over a remark on the entry or a cut-down shape. It is a
`trip_leg` row with `backup_of_id` set. Rejected: a table of its own, which
would be a second copy of twenty columns, of the per-type rules and of the
`PATCH` that judges them.

**`Trip.legs` is filtered in its `primaryjoin`.** Readiness, the dates, the
dashboard, the round-trip rules, the sheet's rows and the frontend all read a
trip's legs, and a backup must count for none of them. Filtering in each reader
is the failure that gets written once and missed on the next one; filtering in
the relationship makes "an entry" the default answer and a backup something you
must ask for. The API follows it: `legs` holds entries, each nesting its
`backups`.

**Unticked backups do not hold a trip back.** A plan B usually is not booked,
and a trip whose plan A is settled is ready.

**One level, no section, no packing list.** A backup of a backup has no meaning
anyone asked for. A backup sits under its entry, so moving the entry moves it
without a second write. A packing-list link is a claim about the journey
actually planned (`uq_trip_leg_packing_list_id`, and a list's date comes from
its leg).

**The downgrade deletes the backups.** Only dropping the column would turn each
one into an ordinary entry of its trip, silently changing what the trip reads
as, which is worse than losing it.

**The self-reference needs no restore-tab change.** `RESTORE_TABS` orders
tables, and a table cannot come before itself, but the sheet holds rows by `id`
and a backup is always created after its entry, so the parent is always
restored first. That is what the next decision, on choosing the main option,
has to preserve.
