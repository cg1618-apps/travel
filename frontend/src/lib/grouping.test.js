import { describe, expect, it } from 'vitest'

import {
  groupByCategory,
  groupForChecklist,
  groupRuns,
  inGroupOrder,
  moveInGroup,
  orderIds,
  rowNumbers,
} from './grouping'

const item = (id, category, name, detail = null) => ({ id, category, name, detail, position: id })

describe('groupRuns', () => {
  it('blanks repeated category and name, like the sheet', () => {
    const rows = groupRuns([
      item(1, '重要', '錢包'),
      item(2, '重要', '鑰匙', '家鑰匙'),
      item(3, '重要', '鑰匙', '宿舍鑰匙'),
      item(4, '3C', '鑰匙'),
    ])
    expect(rows.map((r) => [r.item.id, r.showCategory, r.showName])).toEqual([
      [1, true, true],
      [2, false, true],
      [3, false, false],
      [4, true, true], // a new category restarts the name run too
    ])
  })

  it('treats blank categories as equal to each other', () => {
    const rows = groupRuns([item(1, null, 'a'), item(2, null, 'a', 'b')])
    expect(rows.map((r) => r.showCategory)).toEqual([true, false])
  })
})

describe('groupForChecklist', () => {
  it('puts consecutive same-name items under one heading', () => {
    const groups = groupForChecklist([
      item(1, '重要', '鑰匙', '家鑰匙'),
      item(2, '重要', '鑰匙', '宿舍鑰匙'),
      item(3, '重要', '眼鏡'),
    ])
    expect(groups.map((g) => [g.name, g.items.map((i) => i.id)])).toEqual([
      ['鑰匙', [1, 2]],
      ['眼鏡', [3]],
    ])
  })
})

describe('groupByCategory', () => {
  const at = (id, category, position) => ({ id, category, name: `n${id}`, position })

  it('keeps a category together even when its items are interleaved', () => {
    const groups = groupByCategory([at(1, 'A', 0), at(2, 'B', 1), at(3, 'A', 2)])
    expect(groups.map((g) => [g.category, g.items.map((i) => i.id)])).toEqual([
      ['A', [1, 3]],
      ['B', [2]],
    ])
  })

  it('orders groups by their first item and items by position', () => {
    const groups = groupByCategory([at(1, 'A', 5), at(2, 'B', 1), at(3, 'A', 3)])
    expect(orderIds(groups)).toEqual([2, 3, 1])
  })

  it('puts uncategorised items in a group of their own', () => {
    const groups = groupByCategory([at(1, null, 0), at(2, 'A', 1), at(3, null, 2)])
    expect(groups.map((g) => g.category)).toEqual([null, 'A'])
    expect(inGroupOrder([at(1, null, 0), at(2, 'A', 1), at(3, null, 2)]).map((i) => i.id)).toEqual(
      [1, 3, 2],
    )
  })
})

describe('moveInGroup', () => {
  it('moves within one group and leaves the others alone', () => {
    const groups = groupByCategory([
      { id: 1, category: 'A', position: 0 },
      { id: 2, category: 'A', position: 1 },
      { id: 3, category: 'A', position: 2 },
      { id: 4, category: 'B', position: 3 },
    ])
    expect(orderIds(moveInGroup(groups, 'A', 2, 0))).toEqual([3, 1, 2, 4])
  })
})

describe('groupForChecklist, across categories', () => {
  it('shows a category together even when stored apart', () => {
    const groups = groupForChecklist([
      { id: 1, category: 'A', name: '鑰匙', position: 0 },
      { id: 2, category: 'B', name: '眼鏡', position: 1 },
      { id: 3, category: 'A', name: '鑰匙', position: 2 },
    ])
    expect(groups.map((g) => g.items.map((i) => i.id))).toEqual([[1, 3], [2]])
  })
})

describe('rowNumbers', () => {
  it('numbers rows from 1 in the order the sheet shows them', () => {
    // Position order is 1..4, but 3C's first item sits after 重要's, so 重要's
    // second item (position 3) comes before it.
    const numbers = rowNumbers([
      item(1, '重要', '錢包'),
      item(2, '3C', '充電器'),
      item(3, '重要', '鑰匙'),
      item(4, null, '雨傘'),
    ])
    expect([...numbers]).toEqual([
      [1, 1],
      [3, 2],
      [2, 3],
      [4, 4],
    ])
  })

  it('is empty for an empty list', () => {
    expect(rowNumbers([]).size).toBe(0)
  })
})
