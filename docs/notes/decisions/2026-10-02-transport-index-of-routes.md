# 交通 is an index of routes, and the entry is the route

`/transport` is one card per route, each linking to `/transport/:routeId`, the
shape `/lists` and `/trips` already have.

**The entry is the route, not the option.** A route is what you look up ("how
do I get from 彰化火車站 to 宿舍"), and the options under it only make sense
compared side by side, so they stay together on the route's page.

The index has no tabs: routes have no kinds and no 狀態, so a tab strip would
have one tab.
