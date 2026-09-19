import { describe, expect, test } from 'vitest'

import { TIMINGS, daysUntil, dueTimings, isTimingDue } from './timing'

const DEPARTURE = '2026-10-10'

describe('daysUntil', () => {
  test('counts whole days forward', () => {
    expect(daysUntil(DEPARTURE, '2026-10-08')).toBe(2)
  })

  test('is zero on the day itself', () => {
    expect(daysUntil(DEPARTURE, '2026-10-10')).toBe(0)
  })

  test('goes negative once departure has passed', () => {
    expect(daysUntil(DEPARTURE, '2026-10-12')).toBe(-2)
  })

  test('is null when there is no departure date', () => {
    expect(daysUntil(null, '2026-10-08')).toBeNull()
  })

  test('crosses a month boundary correctly', () => {
    expect(daysUntil('2026-11-01', '2026-10-31')).toBe(1)
  })

  test('is not shifted by the local timezone', () => {
    // A bare YYYY-MM-DD parses as UTC while a full ISO timestamp parses as
    // local, so mixing the two moves dates by a day for most of the world.
    // Passing a real Date must agree with passing the string.
    expect(daysUntil(DEPARTURE, new Date(2026, 9, 8))).toBe(2)
  })
})

describe('dueTimings', () => {
  test('whenever is always due', () => {
    expect(dueTimings(DEPARTURE, '2026-01-01').has('whenever')).toBe(true)
  })

  test('the night before is not due two days out', () => {
    expect(dueTimings(DEPARTURE, '2026-10-08').has('night_before')).toBe(false)
  })

  test('the night before is due when departure is tomorrow', () => {
    expect(dueTimings(DEPARTURE, '2026-10-09').has('night_before')).toBe(true)
  })

  test('the night before is still due on the day itself', () => {
    // `<= 1`, not `=== 1`. A group that stopped being due the moment the day
    // arrived would hide exactly the things not yet packed.
    expect(dueTimings(DEPARTURE, DEPARTURE).has('night_before')).toBe(true)
  })

  test('the day of is not due the night before', () => {
    expect(dueTimings(DEPARTURE, '2026-10-09').has('day_of')).toBe(false)
  })

  test('the day of and just before are due on the day', () => {
    const due = dueTimings(DEPARTURE, DEPARTURE)
    expect(due.has('day_of')).toBe(true)
    expect(due.has('just_before')).toBe(true)
  })

  test('everything stays due after departure has passed', () => {
    // A list you are still working through on the plane must not empty out.
    const due = dueTimings(DEPARTURE, '2026-10-12')
    expect([...due].sort()).toEqual([...TIMINGS].sort())
  })

  test('nothing but whenever is due when the list has no departure date', () => {
    expect([...dueTimings(null, '2026-10-08')]).toEqual(['whenever'])
  })
})

describe('isTimingDue', () => {
  test('agrees with dueTimings', () => {
    expect(isTimingDue('night_before', DEPARTURE, '2026-10-09')).toBe(true)
    expect(isTimingDue('day_of', DEPARTURE, '2026-10-09')).toBe(false)
  })
})

describe('TIMINGS', () => {
  test('renders in escalating order', () => {
    // The screen relies on this order; the API only guarantees the values.
    expect(TIMINGS).toEqual(['whenever', 'night_before', 'day_of', 'just_before'])
  })
})
