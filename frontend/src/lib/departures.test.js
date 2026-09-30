import { describe, expect, it } from 'vitest'

import {
  bucketOf, dayTypeOf, formatDeparture, groupByBucket, nextDeparture, parseDepartureInput,
} from './departures'

describe('bucketOf', () => {
  it('splits the day at 12:00, 14:00 and 18:00', () => {
    expect(bucketOf('11:59')).toBe('morning')
    expect(bucketOf('12:00')).toBe('midday')
    expect(bucketOf('13:59:00')).toBe('midday')
    expect(bucketOf('14:00')).toBe('afternoon')
    expect(bucketOf('17:59')).toBe('afternoon')
    expect(bucketOf('18:00')).toBe('evening')
  })
})

describe('groupByBucket', () => {
  it('sorts within a bucket', () => {
    const groups = groupByBucket([{ time: '08:40' }, { time: '07:00' }, { time: '19:40' }])
    expect(groups.morning.map((d) => d.time)).toEqual(['07:00', '08:40'])
    expect(groups.evening.map((d) => d.time)).toEqual(['19:40'])
    expect(groups.midday).toEqual([])
  })
})

describe('dayTypeOf', () => {
  // UTC instants whose Taipei (UTC+8) weekday is known, so the result does not
  // depend on the timezone of the machine running the tests.
  it('treats Saturday and Sunday in Taipei as holidays', () => {
    expect(dayTypeOf(new Date('2026-09-26T00:00:00Z'))).toBe('holiday') // Sat 08:00 Taipei
    expect(dayTypeOf(new Date('2026-09-27T04:00:00Z'))).toBe('holiday') // Sun 12:00 Taipei
    expect(dayTypeOf(new Date('2026-09-28T04:00:00Z'))).toBe('weekday') // Mon 12:00 Taipei
  })
  it('takes the Taipei day, not the UTC one', () => {
    expect(dayTypeOf(new Date('2026-09-25T16:30:00Z'))).toBe('holiday') // Fri UTC, Sat 00:30 Taipei
    expect(dayTypeOf(new Date('2026-09-27T17:00:00Z'))).toBe('weekday') // Sun UTC, Mon 01:00 Taipei
  })
})

describe('nextDeparture', () => {
  const deps = [
    { id: 1, day_type: 'holiday', time: '07:00:00' },
    { id: 2, day_type: 'holiday', time: '13:40:00' },
    { id: 3, day_type: 'weekday', time: '09:00:00' },
  ]
  it("is the first of today's day type at or after now", () => {
    expect(nextDeparture(deps, new Date('2026-09-26T00:00:00Z')).id).toBe(2) // Sat 08:00 Taipei
    expect(nextDeparture(deps, new Date('2026-09-26T05:40:00Z')).id).toBe(2) // Sat 13:40 Taipei
  })
  it("is null once today's last one has gone", () => {
    expect(nextDeparture(deps, new Date('2026-09-26T12:00:00Z'))).toBeNull() // Sat 20:00 Taipei
  })
  it('reads the clock in Taipei, not on the device', () => {
    // 22:30 UTC Friday is 06:30 Saturday in Taipei: the 07:00 holiday run is next.
    expect(nextDeparture(deps, new Date('2026-09-25T22:30:00Z')).id).toBe(1)
  })
})

describe('parseDepartureInput / formatDeparture', () => {
  it('reads the sheet notation', () => {
    expect(parseDepartureInput('*13:40')).toEqual({ time: '13:40', irregular: true })
    expect(parseDepartureInput(' 7:05 ')).toEqual({ time: '07:05', irregular: false })
    expect(parseDepartureInput('25:00')).toBeNull()
    expect(parseDepartureInput('soon')).toBeNull()
  })
  it('writes it back', () => {
    expect(formatDeparture({ time: '13:40:00', irregular: true })).toBe('*13:40')
    expect(formatDeparture({ time: '07:05:00', irregular: false })).toBe('7:05')
  })
})
