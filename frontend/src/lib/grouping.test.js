import { describe, expect, it } from 'vitest'

import { groupForChecklist, groupRuns } from './grouping'

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
