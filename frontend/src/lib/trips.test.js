import { describe, expect, it } from 'vitest'

import {
  archivePatch,
  firstLine,
  formatArrival,
  formatDuration,
  formatTaipei,
  fromTaipeiInput,
  needsStartDate,
  partitionTrips,
  sortLegs,
  taipeiInputValue,
  templateChoices,
  tripDateRange,
  unlinkedNotice,
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

const t = (id, fields = {}) => ({ id, archived: false, template: false, legs: [], ...fields })

describe('partitionTrips', () => {
  it('puts each trip in exactly one section, archived winning over template', () => {
    const trips = [t(1), t(2, { template: true }), t(3, { archived: true }),
      t(4, { archived: true, template: true }), t(5)]
    const { others, templates, archived } = partitionTrips(trips, 5)
    expect(others.map((x) => x.id)).toEqual([1])
    expect(templates.map((x) => x.id)).toEqual([2])
    expect(archived.map((x) => x.id)).toEqual([3, 4])
  })
  it('excludes nothing when no trip is on screen', () => {
    expect(partitionTrips([t(1)], null).others).toHaveLength(1)
  })
})

describe('templateChoices', () => {
  it('offers every template, archived or not', () => {
    const trips = [t(1), t(2, { template: true }), t(3, { template: true, archived: true })]
    expect(templateChoices(trips).map((x) => x.id)).toEqual([2, 3])
  })
})

describe('needsStartDate', () => {
  it('is true only for a trip with legs', () => {
    expect(needsStartDate(t(1))).toBe(false)
    expect(needsStartDate(t(1, { legs: [{}] }))).toBe(true)
  })
})

describe('unlinkedNotice', () => {
  it('names the leg and the list', () => {
    expect(unlinkedNotice({ from_place: '台北車站', to_place: '彰化火車站', packing_list_name: '台北去彰化' }))
      .toBe('「台北車站 → 彰化火車站」在範本中連結了「台北去彰化」，請自行連結打包清單。')
  })
})

describe('archivePatch', () => {
  it('trims the remark and sends a blank one as null', () => {
    expect(archivePatch('  下次早點訂  ')).toEqual({ archived: true, archive_note: '下次早點訂' })
    expect(archivePatch('   ')).toEqual({ archived: true, archive_note: null })
  })
})

describe('firstLine', () => {
  it('is the first non-empty line, or null', () => {
    expect(firstLine('a\nb')).toBe('a')
    expect(firstLine('\n  \nb')).toBe('b')
    expect(firstLine(null)).toBe(null)
  })
})
