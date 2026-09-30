import { describe, expect, it } from 'vitest'

import { formatPrice, groupByDayType, parsePrice } from './transport'

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

describe('parsePrice', () => {
  it('reads a whole number', () => {
    expect(parsePrice(' 22 ')).toBe(22)
    expect(parsePrice('0')).toBe(0)
  })
  it('reads an empty cell as clearing the price', () => {
    expect(parsePrice('  ')).toBeNull()
  })
  it('refuses what is not a whole number', () => {
    expect(parsePrice('NT$22')).toBeUndefined()
    expect(parsePrice('-5')).toBeUndefined()
    expect(parsePrice('2.5')).toBeUndefined()
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
