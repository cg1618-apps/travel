/**
 * The sheet's grouping. A group is a 類別: every item of one category sits
 * together, and a list with no category on an item has that item in a group
 * of its own (`category === null`).
 *
 * Order lives in `position` and nothing else. A group sits where its first
 * item sits, and its items follow in position order — so reordering rows or
 * whole groups is one write of the list's full order, and the server refuses
 * an order that splits a group.
 *
 * Inside a group the sheet's visual grouping still applies: a category or a
 * name is written once, on the first row of a run, and left blank beneath —
 * exactly how the owner's Google Sheet reads.
 */

const same = (a, b) => (a ?? '') === (b ?? '')

/** Rows as runs: which ones write their category and their name. */
export function groupRuns(items) {
  return items.map((item, index) => {
    const previous = items[index - 1]
    const showCategory = !previous || !same(previous.category, item.category)
    const showName = showCategory || !same(previous.name, item.name)
    return { item, showCategory, showName }
  })
}

/** Items by category, each group ordered by position, groups by their first item. */
export function groupByCategory(items) {
  const groups = new Map()
  for (const item of [...items].sort((a, b) => a.position - b.position)) {
    const key = item.category ?? ''
    if (!groups.has(key)) groups.set(key, { key, category: item.category ?? null, items: [] })
    groups.get(key).items.push(item)
  }
  return [...groups.values()]
}

/** Every item in the order the sheet shows it: grouped, then by position. */
export function inGroupOrder(items) {
  return groupByCategory(items).flatMap((group) => group.items)
}

/** The ids of every item, group after group — the body of a reorder. */
export const orderIds = (groups) => groups.flatMap((group) => group.items.map((item) => item.id))

/** Moves one item inside its group; every other group keeps its place. */
export function moveInGroup(groups, groupKey, from, to) {
  return groups.map((group) => {
    if (group.key !== groupKey) return group
    const items = [...group.items]
    const [moved] = items.splice(from, 1)
    items.splice(to, 0, moved)
    return { ...group, items }
  })
}

/** Consecutive items sharing a category and name, as one heading each. */
export function groupForChecklist(items) {
  const groups = []
  for (const { item, showName } of groupRuns(inGroupOrder(items))) {
    if (showName) groups.push({ key: item.id, name: item.name, items: [item] })
    else groups[groups.length - 1].items.push(item)
  }
  return groups
}
