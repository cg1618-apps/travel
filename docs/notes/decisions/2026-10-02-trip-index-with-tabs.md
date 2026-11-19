# Trips and lists are indexes with tabs; there is no current trip

`/lists` and `/trips` are indexes with one tab per shelf, and 行程 opens
`/trips` the way 打包清單 opens `/lists`.

**There is no current trip.** A page that showed one trip — first picked by
dates, then by usage — was retired rather than refined. Picking by dates
switched trips mid-journey, never chose a trip with no legs, and kept a
finished trip until something newer had a leg. Picking by usage still left a
second place every trip could be: the page left the current trip out of the
sections below it, so a lone 一般 trip sat in no section at all, and code had
to move the page whenever a 狀態 change took the trip out of being current.
What the current trip was for — "what am I using now" — is the dashboard's job,
and the dashboard already shows every 使用中 and 未來使用 trip.

**Tabs, not stacked sections.** Every row is on exactly one tab, the counts say
where without scrolling, and the tabs are the API's four arrays shown as they
come, so the screen cannot drop a row the API returned.

**Shelves are newest `created_at` first, for trips as for lists.** It is stable,
and a trip just created without legs lands at the top of its tab.

Rejected:

- **A current trip pinned above the tabs.** The same trip in two places again,
  and the dashboard already answers the question.
- **Ordering trips by departure.** It is the order of the legs, not of the
  trips: a trip with no legs has none, and editing a leg's time reorders the
  tab.
