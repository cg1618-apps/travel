/**
 * The dashboard's month calendar. Days are Taipei days written `YYYY-MM-DD`,
 * the same as every other date here, so a day is a string and compares as one.
 */

import { taipeiInputValue } from './trips'

const pad = (n) => String(n).padStart(2, '0')

/** `month` is 1-12. */
export const dayKey = (year, month, day) => `${year}-${pad(month)}-${pad(day)}`

/** Today in Taipei, as `{ year, month, day, key }`. */
export function taipeiToday(now = new Date()) {
  const key = taipeiInputValue(now.toISOString()).slice(0, 10)
  const [year, month, day] = key.split('-').map(Number)
  return { year, month, day, key }
}

/** The month before or after, `{ year, month }`. */
export function shiftMonth({ year, month }, by) {
  const index = year * 12 + (month - 1) + by
  return { year: Math.floor(index / 12), month: (index % 12) + 1 }
}

/**
 * Six weeks of seven days, Sunday first, covering the month. Days of the
 * months either side fill the first and last week and are `inMonth: false`.
 */
export function monthGrid({ year, month }) {
  // Calendar arithmetic only, so UTC: no device timezone or DST can shift a day.
  const first = new Date(Date.UTC(year, month - 1, 1))
  const start = Date.UTC(year, month - 1, 1 - first.getUTCDay())
  return Array.from({ length: 6 }, (_, week) =>
    Array.from({ length: 7 }, (_, weekday) => {
      const date = new Date(start + (week * 7 + weekday) * 86400000)
      return {
        key: dayKey(date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate()),
        day: date.getUTCDate(),
        inMonth: date.getUTCMonth() === month - 1,
      }
    }),
  )
}

/** Every Taipei day from `from` to `to`, both `YYYY-MM-DD`, inclusive. */
function daysBetween(from, to) {
  const days = []
  const [y, m, d] = from.split('-').map(Number)
  for (let t = Date.UTC(y, m - 1, d); ; t += 86400000) {
    const date = new Date(t)
    const key = dayKey(date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate())
    if (key > to) return days
    days.push(key)
  }
}

/**
 * Day to the trips on it: each trip covers every Taipei day from its first
 * time to its last, a leg with one time counting it as both its ends. A trip
 * with no times has no days.
 */
export function tripDays(trips) {
  const byDay = new Map()
  for (const trip of trips) {
    const day = (iso) => taipeiInputValue(iso).slice(0, 10)
    const starts = trip.legs.map((leg) => leg.departs_at ?? leg.arrives_at).filter(Boolean).map(day)
    const ends = trip.legs.map((leg) => leg.arrives_at ?? leg.departs_at).filter(Boolean).map(day)
    if (starts.length === 0) continue
    const from = starts.reduce((a, b) => (b < a ? b : a))
    const to = ends.reduce((a, b) => (b > a ? b : a))
    for (const key of daysBetween(from, to)) {
      byDay.set(key, [...(byDay.get(key) ?? []), trip])
    }
  }
  return byDay
}
