import { describe, expect, it } from 'vitest'

import { FILTERS, applyFilters, isFiltering, statusScope, toggleValue, withStatusScope } from './filters'
import { STATUS_LABELS } from './labels'

const items = [
  { id: 1, status: 'packed', timing: 'whenever', need: 'buy', location: '家', needs_double_check: true, double_checked: false },
  { id: 2, status: 'not_packed', timing: 'day_of', need: null, location: null, needs_double_check: false, double_checked: false },
  { id: 3, status: 'not_packed', timing: 'whenever', need: 'buy', location: '宿舍', needs_double_check: true, double_checked: true },
]
const ids = (rows) => rows.map((row) => row.id)

describe('applyFilters', () => {
  it('shows everything when nothing is selected', () => {
    expect(ids(applyFilters(items, {}))).toEqual([1, 2, 3])
    expect(ids(applyFilters(items, { status: [] }))).toEqual([1, 2, 3])
    expect(isFiltering({ status: [] })).toBe(false)
  })

  it('ORs values within a column', () => {
    expect(ids(applyFilters(items, { timing: ['day_of', 'just_before'] }))).toEqual([2])
    expect(ids(applyFilters(items, { status: ['packed', 'not_packed'] }))).toEqual([1, 2, 3])
  })

  it('ANDs columns', () => {
    expect(ids(applyFilters(items, { status: ['not_packed'], need: ['buy'] }))).toEqual([3])
  })

  it('reads Double Check as its three states', () => {
    expect(ids(applyFilters(items, { check: ['needed'] }))).toEqual([1])
    expect(ids(applyFilters(items, { check: ['off'] }))).toEqual([2])
  })

  it('lets a blank 需求 or 取得地點 be picked', () => {
    expect(ids(applyFilters(items, { need: [''] }))).toEqual([2])
    expect(ids(applyFilters(items, { location: [''] }))).toEqual([2])
  })
})

describe('FILTERS', () => {
  it('offers only the locations the list holds, blank last', () => {
    const values = FILTERS.location.values(items)
    expect([...values].sort()).toEqual(['', '宿舍', '家'].sort())
    expect(values.at(-1)).toBe('')
  })

  it('labels every closed value', () => {
    for (const key of ['status', 'check', 'timing', 'need']) {
      for (const value of FILTERS[key].values(items)) expect(FILTERS[key].label(value)).toBeTruthy()
    }
    expect(FILTERS.status.label('packed')).toBe(STATUS_LABELS.packed)
  })
})

describe('toggleValue', () => {
  it('adds then removes', () => {
    const on = toggleValue({}, 'status', 'packed')
    expect(on).toEqual({ status: ['packed'] })
    expect(isFiltering(on)).toBe(true)
    expect(toggleValue(on, 'status', 'packed')).toEqual({ status: [] })
  })
})

describe('statusScope', () => {
  it('is all with no 打包狀態 filter, and not_packed with exactly 未打包', () => {
    expect(statusScope({})).toBe('all')
    expect(statusScope({ status: [] })).toBe('all')
    expect(statusScope({ status: ['not_packed'] })).toBe('not_packed')
  })

  it('is neither for any other choice made in the header', () => {
    expect(statusScope({ status: ['packed'] })).toBe(null)
    expect(statusScope({ status: ['not_packed', 'no_need'] })).toBe(null)
  })

  it('ignores the other columns', () => {
    expect(statusScope({ timing: ['day_of'] })).toBe('all')
  })
})

describe('withStatusScope', () => {
  it('sets only the 打包狀態 filter, leaving the rest', () => {
    const filters = { status: ['packed'], timing: ['day_of'] }
    expect(withStatusScope(filters, 'not_packed')).toEqual({ status: ['not_packed'], timing: ['day_of'] })
    expect(withStatusScope(filters, 'all')).toEqual({ status: [], timing: ['day_of'] })
  })

  it('hides what is packed once applied', () => {
    expect(ids(applyFilters(items, withStatusScope({}, 'not_packed')))).toEqual([2, 3])
  })
})
