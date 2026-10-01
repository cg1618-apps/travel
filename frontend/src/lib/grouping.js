/**
 * The sheet's visual grouping: a category or a name is written once, on the
 * first row of a run, and left blank beneath — exactly how the owner's Google
 * Sheet reads. Only meaningful in position order; the Grid turns it off under
 * any other sort, where a blank cell would be ambiguous.
 */

const same = (a, b) => (a ?? '') === (b ?? '')

export function groupRuns(items) {
  return items.map((item, index) => {
    const previous = items[index - 1]
    const showCategory = !previous || !same(previous.category, item.category)
    const showName = showCategory || !same(previous.name, item.name)
    return { item, showCategory, showName }
  })
}

/** Consecutive items sharing a category and name, as one heading each. */
export function groupForChecklist(items) {
  const groups = []
  for (const { item, showName } of groupRuns(items)) {
    if (showName) groups.push({ key: item.id, name: item.name, items: [item] })
    else groups[groups.length - 1].items.push(item)
  }
  return groups
}
