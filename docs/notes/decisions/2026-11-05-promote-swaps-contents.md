# Choosing the main option swaps contents, not rows

**設為主要 swaps the two rows' contents and leaves `backup_of_id` alone.**
Rejected: pointing the entry at the backup and re-parenting its siblings. It
reads more directly, but the parent would then have the higher id, and
`backup_of_id` is an immediate foreign key, so the next restore would refuse a
sheet the app itself wrote — and nothing would say so until that restore was
needed. It would also have to move the section and the packing list across and
order those writes around `uq_trip_leg_packing_list_id`, all of which the swap
gets by not moving them.

**What stays is named, and everything else swaps** (`_STAYS_WITH_THE_ROW` in
`app/services/domain/trip.py`). A list of what moves would have to be
remembered by every new column, and a column it missed would leave part of a
booking behind on the wrong option with nothing to show for it.

**The section and the packing list stay with the entry.** Both describe the
journey being made rather than one way of making it, which is also why a backup
has neither. So a list's date follows the option now chosen.
