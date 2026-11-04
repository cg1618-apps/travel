import { describe, expect, it } from 'vitest'

import {
  autofillName, badgeFor, everyRow, hasEnded, isAutoSaved, legsByList, linkChoices, linkLabel,
  onDashboard, rowEnd, rowStart, statusLabel, TABS, tabCounts, tabFor, tabFromSearch,
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

// The dashboard rule's cases, all here and nowhere else in this file. They are
// `tests/unit/test_dashboard_rule.py`'s, row for row, which pins `on_dashboard`
// to the same answers. A row's `start` is what `rowStart` would compute, as ms
// (null for none), so the rule is tested apart from how a start is found.
const at = (day) => new Date(`${day}T00:00:00+08:00`).getTime()
const T = new Date('2026-11-04T09:00:00+08:00').getTime()
const HOUR = 3_600_000
const DAY = 24 * HOUR
const startRow = (id, kind, usage, start = null) => ({ ...row(id, kind, usage), start })
const DASHBOARD_CASES = [
  {
    name: 'keeps in-use and upcoming free rows, order kept without starts',
    rows: [startRow(1, 'free', 'upcoming'), startRow(2, 'free', 'unused'), startRow(3, 'free', 'in_use'),
      startRow(4, 'free', 'past'), startRow(5, 'saved'), startRow(6, 'free', 'upcoming'),
      startRow(7, 'free', 'in_use')],
    // Every row ties with no start, so the incoming order stands: 使用中 no
    // longer goes first.
    expected: [1, 3, 6, 7],
  },
  {
    name: 'soonest start first and no start last',
    rows: [startRow(1, 'free', 'in_use'), startRow(2, 'free', 'upcoming', T + 2 * DAY),
      startRow(3, 'free', 'in_use', T), startRow(4, 'free', 'upcoming'),
      startRow(5, 'free', 'upcoming', T + HOUR)],
    expected: [3, 5, 2, 1, 4],
  },
  {
    name: 'equal starts keep the incoming order',
    rows: [startRow(1, 'free', 'upcoming', T), startRow(2, 'free', 'in_use', T)],
    expected: [1, 2],
  },
  {
    name: 'a template or saved row is never current',
    rows: [startRow(1, 'template'), startRow(2, 'saved')],
    expected: [],
  },
]

describe('onDashboard', () => {
  for (const { name, rows, expected } of DASHBOARD_CASES) {
    it(name, () => {
      expect(onDashboard(rows, (r) => r.start ?? null).map((r) => r.id)).toEqual(expected)
    })
  }
})

describe('rowStart', () => {
  it("is a trip's earliest departure, ignoring legs with none", () => {
    const trip = { legs: [
      { departs_at: '2026-11-06T09:00:00+08:00' }, { departs_at: null },
      { departs_at: '2026-11-05T22:00:00+08:00' }] }
    expect(rowStart(trip)).toBe(new Date('2026-11-05T22:00:00+08:00').getTime())
    expect(rowStart({ legs: [{ departs_at: null, arrives_at: '2026-11-05T22:00:00+08:00' }] })).toBeNull()
    expect(rowStart({ legs: [] })).toBeNull()
  })
  it("is a list's date at Taipei midnight", () => {
    expect(rowStart({ departure_at: '2026-11-05' })).toBe(at('2026-11-05'))
    expect(rowStart({ departure_at: null })).toBeNull()
  })
  it('is what the screen sorts by', () => {
    const trips = [{ ...row(1, 'free', 'in_use'), legs: [] },
      { ...row(2, 'free', 'upcoming'), legs: [{ departs_at: '2026-11-05T08:00:00+08:00' }] }]
    expect(onDashboard(trips).map((r) => r.id)).toEqual([2, 1])
  })
})

describe('rowEnd and hasEnded', () => {
  const now = new Date('2026-11-04T12:00:00+08:00')
  it('ends a trip at its latest arrival, else departure', () => {
    const trip = { legs: [
      { departs_at: '2026-11-03T08:00:00+08:00', arrives_at: '2026-11-03T10:00:00+08:00' },
      { departs_at: '2026-11-04T09:00:00+08:00', arrives_at: null }] }
    expect(rowEnd(trip)).toBe(new Date('2026-11-04T09:00:00+08:00').getTime())
    expect(hasEnded(trip, now)).toBe(true)
    expect(hasEnded({ legs: [{ departs_at: '2026-11-04T13:00:00+08:00', arrives_at: null }] }, now))
      .toBe(false)
  })
  it('has no end, and no badge, for a trip with no times', () => {
    expect(rowEnd({ legs: [{ departs_at: null, arrives_at: null }] })).toBeNull()
    expect(hasEnded({ legs: [] }, now)).toBe(false)
  })
  it('ends a linked list at its leg, an unlinked one at the end of its Taipei day', () => {
    const list = { id: 7, departure_at: '2026-11-04' }
    const legs = legsByList([{ legs: [
      { packing_list_id: 7, departs_at: '2026-11-04T08:00:00+08:00', arrives_at: '2026-11-04T10:00:00+08:00' },
    ] }])
    expect(hasEnded(list, now, legs)).toBe(true)
    expect(hasEnded(list, now)).toBe(false)
    expect(rowEnd(list)).toBe(at('2026-11-05'))
    expect(hasEnded({ id: 8, departure_at: '2026-11-03' }, now)).toBe(true)
    expect(hasEnded({ id: 9, departure_at: null }, now)).toBe(false)
  })
  it("falls back to the list's day when the linked leg has no time", () => {
    const legs = legsByList([{ legs: [{ packing_list_id: 7, departs_at: null, arrives_at: null }] }])
    expect(rowEnd({ id: 7, departure_at: '2026-11-04' }, legs)).toBe(at('2026-11-05'))
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

describe('statusLabel', () => {
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
  it('puts the list date after the name when it has one', () => {
    expect(linkLabel({ ...at(1, 'free', '2026-09-02T00:00:00Z', 'upcoming'), departure_at: '2026-10-03' }))
      .toBe('L1 (2026-10-03) · 2026-09-02 · 未來使用')
    expect(linkLabel({ ...at(3, 'saved', '2026-09-02T00:00:00Z'), departure_at: null }))
      .toBe('L3 · 2026-09-02 · 保存')
  })
})
