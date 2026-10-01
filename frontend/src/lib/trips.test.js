import { describe, expect, it } from 'vitest'

import {
  formatArrival,
  formatDuration,
  formatTaipei,
  fromTaipeiInput,
  sortLegs,
  taipeiInputValue,
  tripDateRange,
} from './trips'

describe('formatDuration', () => {
  it('matches the sheet format', () => {
    expect(formatDuration('2026-09-24T18:06:00+08:00', '2026-09-24T20:59:00+08:00')).toBe('2h53m')
    expect(formatDuration('2026-09-28T12:15:00+08:00', '2026-09-28T14:23:00+08:00')).toBe('2h08m')
    expect(formatDuration('2026-09-28T12:15:00+08:00', '2026-09-28T12:22:00+08:00')).toBe('7m')
  })
})

describe('Taipei conversions', () => {
  it('shows a UTC instant in Taipei time', () => {
    expect(formatTaipei('2026-09-24T10:06:00Z')).toBe('Thu 09/24 18:06')
  })
  it('round-trips an input value', () => {
    expect(taipeiInputValue('2026-09-23T16:30:00Z')).toBe('2026-09-24T00:30')
    expect(fromTaipeiInput('2026-09-24T00:30')).toBe('2026-09-24T00:30:00+08:00')
  })
})

describe('formatArrival', () => {
  it('shows only the clock on the same Taipei day', () => {
    expect(formatArrival('2026-09-24T18:06:00+08:00', '2026-09-24T20:59:00+08:00')).toBe('20:59')
  })
  it('shows the day when the arrival is after Taipei midnight', () => {
    expect(formatArrival('2026-09-24T23:30:00+08:00', '2026-09-25T01:10:00+08:00')).toBe(
      'Fri 09/25 01:10',
    )
  })
  it('judges the day in Taipei, not UTC', () => {
    // 16:30Z and 17:30Z are 00:30 and 01:30 on the 25th in Taipei: one day.
    expect(formatArrival('2026-09-24T16:30:00Z', '2026-09-24T17:30:00Z')).toBe('01:30')
  })
})

describe('tripDateRange', () => {
  const leg = (departs_at, arrives_at) => ({ departs_at, arrives_at })
  it('is null for a trip with no legs', () => {
    expect(tripDateRange([])).toBeNull()
  })
  it('is one date when every leg is on the same day', () => {
    expect(tripDateRange([leg('2026-09-24T08:00:00+08:00', '2026-09-24T10:00:00+08:00')])).toBe('09/24')
  })
  it('spans the first departure to the last arrival whatever the order', () => {
    expect(
      tripDateRange([
        leg('2026-09-28T12:00:00+08:00', '2026-09-28T14:00:00+08:00'),
        leg('2026-09-24T08:00:00+08:00', '2026-09-24T10:00:00+08:00'),
      ]),
    ).toBe('09/24 – 09/28')
  })
})

describe('sortLegs', () => {
  it('orders by departure without changing the input', () => {
    const legs = [{ departs_at: '2026-09-28T12:00:00+08:00' }, { departs_at: '2026-09-24T08:00:00+08:00' }]
    expect(sortLegs(legs)[0]).toBe(legs[1])
    expect(legs[0].departs_at).toBe('2026-09-28T12:00:00+08:00')
  })
})
