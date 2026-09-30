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
  it('treats Saturday and Sunday as holidays', () => {
    expect(dayTypeOf(new Date(2026, 8, 26))).toBe('holiday') // Sat
    expect(dayTypeOf(new Date(2026, 8, 27))).toBe('holiday') // Sun
    expect(dayTypeOf(new Date(2026, 8, 28))).toBe('weekday') // Mon
  })
})

describe('nextDeparture', () => {
  const deps = [
    { id: 1, day_type: 'holiday', time: '07:00:00' },
    { id: 2, day_type: 'holiday', time: '13:40:00' },
    { id: 3, day_type: 'weekday', time: '09:00:00' },
  ]
  it('is the first of today\'s day type at or after now', () => {
    expect(nextDeparture(deps, new Date(2026, 8, 26, 8, 0)).id).toBe(2)
    expect(nextDeparture(deps, new Date(2026, 8, 26, 13, 40)).id).toBe(2)
  })
  it('is null once today\'s last one has gone', () => {
    expect(nextDeparture(deps, new Date(2026, 8, 26, 20, 0))).toBeNull()
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
