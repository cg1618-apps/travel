import { describe, expect, it } from 'vitest'

import { formatPrice, groupByDayType } from './transport'

describe('formatPrice', () => {
  it('shows a price with its currency', () => {
    expect(formatPrice(22)).toBe('NT$22')
  })
  it('shows a free ride as NT$0 rather than as unset', () => {
    expect(formatPrice(0)).toBe('NT$0')
  })
  it('leaves an unset price unset', () => {
    expect(formatPrice(null)).toBeNull()
  })
})

describe('groupByDayType', () => {
  const d = (id, day_type) => ({ id, day_type, time: '08:00', irregular: false })
  it('splits by day type whatever order the API sent', () => {
    const groups = groupByDayType([d(1, 'holiday'), d(2, 'weekday'), d(3, 'holiday')])
    expect(groups.weekday.map((x) => x.id)).toEqual([2])
    expect(groups.holiday.map((x) => x.id)).toEqual([1, 3])
  })
  it('always has both rows, empty when there are no departures', () => {
    expect(groupByDayType([])).toEqual({ weekday: [], holiday: [] })
  })
  it('keeps the weekday row first', () => {
    expect(Object.keys(groupByDayType([d(1, 'holiday')]))).toEqual(['weekday', 'holiday'])
  })
})
