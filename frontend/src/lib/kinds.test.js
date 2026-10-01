import { describe, expect, it } from 'vitest'

import { badgeFor, everyRow, isAutoSaved, leavesCurrent, onDashboard, templateName } from './kinds'

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

describe('templateName and leavesCurrent', () => {
  it('suffixes 範本', () => expect(templateName('札幌')).toBe('札幌（範本）'))
  it('is true for saving or a usage that is not current', () => {
    expect(leavesCurrent({ kind: 'saved' })).toBe(true)
    expect(leavesCurrent({ usage: 'past' })).toBe(true)
    expect(leavesCurrent({ usage: 'unused' })).toBe(true)
    expect(leavesCurrent({ usage: 'upcoming' })).toBe(false)
    expect(leavesCurrent({ usage: 'in_use' })).toBe(false)
    expect(leavesCurrent({ name: 'x' })).toBe(false)
  })
})
