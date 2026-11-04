import { describe, expect, it } from 'vitest'

import {
  fillArrival,
  firstDeparture,
  firstLine,
  formatArrival,
  formatDuration,
  formatLegTimes,
  formatTaipei,
  fromTaipeiInput,
  legSummary,
  needsStartDate,
  readinessBadges,
  readinessHint,
  sortLegs,
  taipeiInputValue,
  tripDateRange,
  tripReadiness,
  unlinkedNotice,
} from './trips'

describe('formatDuration', () => {
  it('matches the sheet format', () => {
    expect(formatDuration('2026-09-24T18:06:00+08:00', '2026-09-24T20:59:00+08:00')).toBe('2h53m')
    expect(formatDuration('2026-09-28T12:15:00+08:00', '2026-09-28T14:23:00+08:00')).toBe('2h08m')
    expect(formatDuration('2026-09-28T12:15:00+08:00', '2026-09-28T12:22:00+08:00')).toBe('7m')
  })
  it('is null when either time is unset', () => {
    expect(formatDuration(null, '2026-09-28T12:22:00+08:00')).toBeNull()
    expect(formatDuration('2026-09-28T12:15:00+08:00', null)).toBeNull()
  })
})

describe('formatLegTimes', () => {
  const d = '2026-09-24T18:06:00+08:00'
  const a = '2026-09-24T20:59:00+08:00'
  it('shows both ends and the duration', () => {
    expect(formatLegTimes({ departs_at: d, arrives_at: a })).toBe('Thu 09/24 18:06 – 20:59 · 2h53m')
  })
  it('shows the departure alone when that is all it has, or the two are equal', () => {
    expect(formatLegTimes({ departs_at: d, arrives_at: null })).toBe('Thu 09/24 18:06')
    expect(formatLegTimes({ departs_at: d, arrives_at: d })).toBe('Thu 09/24 18:06')
  })
  it('marks an arrival with no departure, and is null with neither', () => {
    expect(formatLegTimes({ departs_at: null, arrives_at: a })).toBe('– Thu 09/24 20:59')
    expect(formatLegTimes({ departs_at: null, arrives_at: null })).toBeNull()
  })
})

describe('fillArrival', () => {
  it('fills an empty arrival with the departure and keeps a set one', () => {
    expect(fillArrival('2026-09-24T18:06', '')).toBe('2026-09-24T18:06')
    expect(fillArrival('2026-09-24T18:06', '2026-09-24T20:00')).toBe('2026-09-24T20:00')
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
  it('uses the one time a leg has, and is null when no leg has any', () => {
    expect(tripDateRange([leg(null, null)])).toBeNull()
    expect(
      tripDateRange([
        leg('2026-09-24T08:00:00+08:00', null),
        leg(null, '2026-09-26T10:00:00+08:00'),
        leg(null, null),
      ]),
    ).toBe('09/24 – 09/26')
  })
})

describe('sortLegs', () => {
  it('orders by departure without changing the input', () => {
    const legs = [{ departs_at: '2026-09-28T12:00:00+08:00' }, { departs_at: '2026-09-24T08:00:00+08:00' }]
    expect(sortLegs(legs)[0]).toBe(legs[1])
    expect(legs[0].departs_at).toBe('2026-09-28T12:00:00+08:00')
  })
  it('puts legs with no departure last, then orders by id', () => {
    const legs = [
      { id: 4, departs_at: null },
      { id: 3, departs_at: '2026-09-24T08:00:00+08:00' },
      { id: 2, departs_at: null },
      { id: 1, departs_at: '2026-09-24T08:00:00+08:00' },
    ]
    expect(sortLegs(legs).map((l) => l.id)).toEqual([1, 3, 2, 4])
  })
})

describe('firstDeparture', () => {
  it('is the earliest set departure, or null', () => {
    expect(firstDeparture([{ departs_at: null }, { departs_at: '2026-09-24T00:00:00Z' }]))
      .toBe('2026-09-24T00:00:00.000Z')
    expect(firstDeparture([{ departs_at: null }])).toBeNull()
  })
})

describe('tripReadiness', () => {
  const leg = (fields) => ({
    transport_type: 'other', booked: false, paid: false, collected: false,
    has_booked: true, has_paid: true, has_collected: true, has_booking_code: true, ...fields,
  })
  const ticked = { booked: true, paid: true, collected: true }
  it('is ready once tickets are settled and every shown tick is ticked', () => {
    const r = tripReadiness({ ticket_status: 'bought', legs: [leg(ticked)] })
    expect(r).toEqual({ ready: true, ticketsMissing: false, untickedLegs: 0 })
    expect(readinessHint(r)).toBeNull()
    expect(tripReadiness({ ticket_status: 'not_needed', legs: [] }).ready).toBe(true)
  })
  it('is not ready while tickets are not bought', () => {
    const r = tripReadiness({ ticket_status: 'not_bought', legs: [leg(ticked)] })
    expect(r.ready).toBe(false)
    expect(readinessHint(r)).toBe('未買票')
  })
  it('counts legs with a shown tick left unticked', () => {
    const r = tripReadiness({
      ticket_status: 'bought',
      legs: [leg({ booked: true }), leg(ticked), leg({ transport_type: 'walk' })],
    })
    expect(r).toEqual({ ready: false, ticketsMissing: false, untickedLegs: 1 })
    expect(readinessHint({ ...r, ticketsMissing: true })).toBe('未買票、還有未完成的標籤')
  })
  it('ignores a tick the entry has switched off, and the booking code', () => {
    const r = tripReadiness({
      ticket_status: 'bought',
      legs: [leg({ ...ticked, has_collected: false, collected: false, booking_code: null })],
    })
    expect(r.ready).toBe(true)
  })
  it('counts a fixed tick even when the row says it is switched off', () => {
    const r = tripReadiness({
      ticket_status: 'bought',
      legs: [leg({ transport_type: 'hsr', ...ticked, has_paid: false, paid: false })],
    })
    expect(r.ready).toBe(false)
  })
})

const t = (id, fields = {}) => ({ id, legs: [], ...fields })

describe('needsStartDate', () => {
  it('is true only for a trip with a leg that has a departure', () => {
    expect(needsStartDate(t(1))).toBe(false)
    expect(needsStartDate(t(1, { legs: [{ departs_at: null }] }))).toBe(false)
    expect(needsStartDate(t(1, { legs: [{ departs_at: '2026-09-24T00:00:00Z' }] }))).toBe(true)
  })
})

describe('unlinkedNotice', () => {
  it('names the leg and the list', () => {
    expect(unlinkedNotice({ from_place: '台北車站', to_place: '彰化火車站', packing_list_name: '台北去彰化' }))
      .toBe('「台北車站 → 彰化火車站」在範本中連結了「台北去彰化」，請自行連結打包清單。')
  })
})

describe('firstLine', () => {
  it('is the first non-empty line, or null', () => {
    expect(firstLine('a\nb')).toBe('a')
    expect(firstLine('\n  \nb')).toBe('b')
    expect(firstLine(null)).toBe(null)
  })
})

describe('legSummary', () => {
  const leg = {
    from_place: '台北', to_place: '東京', service: '長榮',
    departs_at: '2026-10-12T00:30:00Z', arrives_at: '2026-10-12T03:40:00Z',
  }
  it('is route, Taipei departure, duration and 車種', () => {
    expect(legSummary(leg)).toBe('台北 → 東京 · Mon 10/12 08:30 · 3h10m · 長榮')
  })
  it('leaves out a blank 車種', () => {
    expect(legSummary({ ...leg, service: null })).toBe('台北 → 東京 · Mon 10/12 08:30 · 3h10m')
    expect(legSummary({ ...leg, service: '  ' })).toBe('台北 → 東京 · Mon 10/12 08:30 · 3h10m')
  })
  it('copes with unset times', () => {
    expect(legSummary({ ...leg, arrives_at: null })).toBe('台北 → 東京 · Mon 10/12 08:30 · 長榮')
    expect(legSummary({ ...leg, departs_at: null })).toBe('台北 → 東京 · 抵達 Mon 10/12 11:40 · 長榮')
    expect(legSummary({ ...leg, departs_at: null, arrives_at: null })).toBe('台北 → 東京 · 長榮')
    expect(legSummary({ ...leg, arrives_at: leg.departs_at })).toBe('台北 → 東京 · Mon 10/12 08:30 · 長榮')
  })
})

describe('readinessBadges', () => {
  it('says 已準備完成 or 未準備完成, then the tickets unless none are needed', () => {
    expect(readinessBadges({ kind: 'free', done: true, ticket_status: 'bought' }))
      .toEqual(['已準備完成', '已買票'])
    expect(readinessBadges({ kind: 'saved', done: false, ticket_status: 'not_bought' }))
      .toEqual(['未準備完成', '未買票'])
    expect(readinessBadges({ kind: 'free', done: false, ticket_status: 'not_needed' }))
      .toEqual(['未準備完成'])
  })
  it('gives a template none', () => {
    expect(readinessBadges({ kind: 'template', done: false, ticket_status: 'not_bought' })).toEqual([])
  })
})
