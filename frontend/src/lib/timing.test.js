import { describe, expect, test } from 'vitest'

import { TIMINGS, daysUntil } from './timing'

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

describe('TIMINGS', () => {
  test('is in escalating order, which is how the When column sorts', () => {
    expect(TIMINGS).toEqual(['whenever', 'night_before', 'day_of', 'just_before'])
  })
})
