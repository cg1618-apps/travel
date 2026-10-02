import { describe, expect, it } from 'vitest'

import {
  autofillName, badgeFor, everyRow, isAutoSaved, linkChoices, linkLabel, onDashboard,
  statusLabel, TABS, tabCounts, tabFor, tabFromSearch, templateName,
} from './kinds'

const row = (id, kind = 'free', usage = kind === 'free' ? 'unused' : null) => ({ id, kind, usage })

describe('isAutoSaved and badgeFor', () => {
  it('reads auto-saved from free + past only', () => {
    expect(isAutoSaved(row(1, 'free', 'past'))).toBe(true)
    expect(isAutoSaved(row(2, 'free', 'in_use'))).toBe(false)
    expect(isAutoSaved(row(3, 'saved'))).toBe(false)
  })
  it('names every kind but plain free', () => {
    expect([row(1, 'template'), row(2, 'saved'), row(3, 'free', 'past'), row(4)].map(badgeFor))
      .toEqual(['範本', '保存', '自動保存', null])
  })
})

describe('onDashboard', () => {
  it('keeps in-use and upcoming free rows, in-use first, order otherwise kept', () => {
    const rows = [row(1, 'free', 'upcoming'), row(2, 'free', 'unused'), row(3, 'free', 'in_use'),
      row(4, 'free', 'past'), row(5, 'saved'), row(6, 'free', 'upcoming'), row(7, 'free', 'in_use')]
    expect(onDashboard(rows).map((r) => r.id)).toEqual([3, 7, 1, 6])
  })
})

describe('everyRow', () => {
  it('concatenates the four shelves once each', () => {
    const index = { free: [row(1)], auto_saved: [row(2)], saved: [row(3)], templates: [row(4)] }
    expect(everyRow(index).map((r) => r.id)).toEqual([1, 2, 3, 4])
  })
  it('lists a row that appears twice only once', () => {
    const index = { free: [row(1)], auto_saved: [], saved: [row(1)], templates: [] }
    expect(everyRow(index).map((r) => r.id)).toEqual([1])
  })
})

describe('templateName and statusLabel', () => {
  it('suffixes 範本', () => expect(templateName('札幌')).toBe('札幌（範本）'))
  it('names usage for free rows and kind otherwise', () => {
    expect([row(1, 'free', 'in_use'), row(2, 'free', 'past'), row(3, 'saved'), row(4, 'template')]
      .map(statusLabel)).toEqual(['使用中', '過去使用', '保存', '範本'])
  })
})

describe('tabs', () => {
  it('are 一般, 範本, 保存, 自動保存 in that order', () => {
    expect(TABS.map((tab) => tab.label)).toEqual(['一般', '範本', '保存', '自動保存'])
    expect(TABS.map((tab) => tab.shelf)).toEqual(['free', 'templates', 'saved', 'auto_saved'])
  })
  it('reads ?tab=, falling back to 一般 for absent or unknown values', () => {
    expect(tabFromSearch('saved')).toBe('saved')
    expect(tabFromSearch('auto_saved')).toBe('auto_saved')
    expect(tabFromSearch(null)).toBe('free')
    expect(tabFromSearch('archived')).toBe('free')
  })
  it('knows which tab a row is on', () => {
    expect([row(1), row(2, 'free', 'past'), row(3, 'saved'), row(4, 'template')].map(tabFor))
      .toEqual(['free', 'auto_saved', 'saved', 'template'])
  })
  it('counts each shelf, 自動保存 against its limit', () => {
    const index = { free: [row(1), row(2)], templates: [row(3)], saved: [], auto_saved: [row(4)] }
    expect(tabCounts(index, 5)).toEqual({ free: '2', template: '1', saved: '0', auto_saved: '1 / 5' })
  })
})

describe('autofillName', () => {
  it('fills an empty name from the source, without （範本）', () => {
    expect(autofillName({ current: '', lastFill: '', source: '札幌（範本）' }))
      .toEqual({ name: '札幌', fill: '札幌' })
  })
  it('replaces its own earlier fill when the source changes', () => {
    expect(autofillName({ current: '札幌', lastFill: '札幌', source: '大阪' }))
      .toEqual({ name: '大阪', fill: '大阪' })
  })
  it('never overwrites a typed name', () => {
    expect(autofillName({ current: '札幌冬天', lastFill: '札幌', source: '大阪' }))
      .toEqual({ name: '札幌冬天', fill: '大阪' })
  })
  it('clears its own fill when the source is removed', () => {
    expect(autofillName({ current: '札幌', lastFill: '札幌', source: null }))
      .toEqual({ name: '', fill: '' })
  })
})

describe('linkChoices and linkLabel', () => {
  const at = (id, kind, created, usage) => ({
    ...row(id, kind, usage ?? (kind === 'free' ? 'unused' : null)),
    name: `L${id}`, created_at: created,
  })
  const index = {
    free: [at(1, 'free', '2026-09-01T00:00:00Z')],
    auto_saved: [at(2, 'free', '2026-09-03T00:00:00Z', 'past')],
    saved: [at(3, 'saved', '2026-09-02T00:00:00Z')],
    templates: [at(4, 'template', '2026-09-04T00:00:00Z')],
  }
  it('offers no templates, newest created first', () => {
    expect(linkChoices(index, null).map((r) => r.id)).toEqual([2, 3, 1])
  })
  it('keeps a template the leg is already linked to', () => {
    expect(linkChoices(index, 4).map((r) => r.id)).toEqual([4, 2, 3, 1])
  })
  it('labels name, Taipei created date and status', () => {
    // 2026-09-02T20:00Z is already 09-03 in Taipei.
    expect(linkLabel({ ...at(1, 'free', '2026-09-02T20:00:00Z', 'in_use') }))
      .toBe('L1 · 2026-09-03 · 使用中')
    expect(linkLabel(at(3, 'saved', '2026-09-02T00:00:00Z'))).toBe('L3 · 2026-09-02 · 保存')
  })
})
