# A trip's `notes` is the overall remark; each section has its own

Every trip has one overall remark, `notes`, one-way or round trip, with
`outbound_title`, `outbound_notes`, `return_title` and `return_notes` beside it.
Toggling round trip moves no text between columns and cannot lose any.

Rejected: **a new `overall_notes`, with `notes` kept as 去程's remark.** It
would have spared text already written on round trips, but a one-way trip's
remark would then become 去程's the moment the trip turned round — the wrong
answer on every trip from then on. The owner said no data migration was
needed.

**Switching back to one-way is refused while 回程 holds anything.** Moving the
回程 entries into the one list, or keeping the 回程 remark hidden, would change
or hide something the owner wrote without asking.

**An entry's `section` is forced to match the trip**, so a section never
disagrees with the trip it is on. **A copy carries `round_trip` and the
sections' titles and remarks**, because it carries each entry's `section`, and
sections on a one-way trip would be meaningless: the shape of the trip is
definition.
