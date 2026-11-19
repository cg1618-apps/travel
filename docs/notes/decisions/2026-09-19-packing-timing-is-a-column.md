# Packing timing is a column, not the layout

Packing timing (`whenever`, `night_before`, `day_of`, `just_before`) was
designed to drive the list screen: items grouped by timing, with the groups
that had fallen due highlighted. It is an ordinary column instead, 打包時機,
offered in escalating rather than alphabetical order.

Rejected, after it had been built and looked at: grouping by timing and
due-now highlighting. The highlight competed with the list for attention, and
the grouping hid things. The same review rejected a "When / Category / Bag"
grouping toggle, because it put the data model's vocabulary on screen and
asked the reader a question about it (`frontend.md`, "Two views").

What survives is `daysUntil`, which says 明天出發: "leaving tomorrow" is still
worth saying, and is a date boundary worth testing on the frontend, where the
viewer's calendar day is the one that matters.
