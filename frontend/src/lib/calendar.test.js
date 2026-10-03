import { describe, expect, it } from 'vitest'

import { monthGrid, shiftMonth, taipeiToday, tripDays } from './calendar'

describe('monthGrid', () => {
  // October 2026 starts on a Thursday, as in the owner's screenshot.
  const grid = monthGrid({ year: 2026, month: 10 })
  it('is six weeks of seven days', () => {
    expect(grid).toHaveLength(6)
    expect(grid.every((week) => week.length === 7)).toBe(true)
  })
  it('starts on the Sunday before the 1st, filling from September', () => {
    expect(grid[0].map((d) => d.day)).toEqual([27, 28, 29, 30, 1, 2, 3])
    expect(grid[0].map((d) => d.inMonth)).toEqual([false, false, false, false, true, true, true])
    expect(grid[0][0].key).toBe('2026-09-27')
  })
  it('ends with November days', () => {
    expect(grid[5].map((d) => d.key)).toEqual([
      '2026-11-01', '2026-11-02', '2026-11-03', '2026-11-04',
      '2026-11-05', '2026-11-06', '2026-11-07',
    ])
  })
  it('starts on the 1st itself when the 1st is a Sunday', () => {
    expect(monthGrid({ year: 2026, month: 11 })[0][0].key).toBe('2026-11-01')
  })
})

describe('shiftMonth', () => {
  it('crosses years both ways', () => {
    expect(shiftMonth({ year: 2026, month: 12 }, 1)).toEqual({ year: 2027, month: 1 })
    expect(shiftMonth({ year: 2026, month: 1 }, -1)).toEqual({ year: 2025, month: 12 })
    expect(shiftMonth({ year: 2026, month: 10 }, 0)).toEqual({ year: 2026, month: 10 })
  })
})

describe('taipeiToday', () => {
  it('is the Taipei day, not the UTC one', () => {
    // 17:00Z on the 2nd is already 01:00 on the 3rd in Taipei.
    expect(taipeiToday(new Date('2026-10-02T17:00:00Z'))).toEqual({ year: 2026, month: 10, day: 3, key: '2026-10-03' })
  })
})

describe('tripDays', () => {
  const leg = (departs_at, arrives_at) => ({ departs_at, arrives_at })
  const trip = (id, legs) => ({ id, name: `T${id}`, legs })
  it('covers every day from the first departure to the last arrival', () => {
    const days = tripDays([
      trip(1, [
        leg('2026-09-28T12:00:00+08:00', '2026-09-28T14:00:00+08:00'),
        leg('2026-09-24T18:00:00+08:00', '2026-09-24T21:00:00+08:00'),
      ]),
    ])
    expect([...days.keys()]).toEqual([
      '2026-09-24', '2026-09-25', '2026-09-26', '2026-09-27', '2026-09-28',
    ])
  })
  it('judges days in Taipei and crosses a month end', () => {
    // 16:30Z on 09-30 is 00:30 on 10-01 in Taipei.
    const days = tripDays([trip(1, [leg('2026-09-29T20:00:00Z', '2026-09-30T16:30:00Z')])])
    expect([...days.keys()]).toEqual(['2026-09-30', '2026-10-01'])
  })
  it('lists every trip on a shared day, and none for a trip with no legs', () => {
    const days = tripDays([
      trip(1, [leg('2026-10-05T08:00:00+08:00', '2026-10-05T10:00:00+08:00')]),
      trip(2, [leg('2026-10-05T18:00:00+08:00', '2026-10-06T01:00:00+08:00')]),
      trip(3, []),
    ])
    expect(days.get('2026-10-05').map((t) => t.id)).toEqual([1, 2])
    expect(days.get('2026-10-06').map((t) => t.id)).toEqual([2])
    expect(days.size).toBe(2)
  })
})
