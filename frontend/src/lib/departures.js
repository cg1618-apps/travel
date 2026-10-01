/**
 * Departure times: the sheet's 早/中/下午/晚 columns, computed from the clock.
 *
 * `now` is always a parameter, never a `new Date()` inside, so tests can stand
 * on a boundary. Weekday vs holiday is Monday–Friday vs Saturday–Sunday;
 * public holidays are not modelled. The weekday and the clock are read in
 * Asia/Taipei, like every leg time, whatever timezone the device is in.
 */

import { TAIPEI } from './trips'

export const BUCKETS = ['morning', 'midday', 'afternoon', 'evening']

const minutes = (time) => {
  const [h, m] = time.split(':').map(Number)
  return h * 60 + m
}

export function bucketOf(time) {
  const m = minutes(time)
  if (m < 12 * 60) return 'morning'
  if (m < 14 * 60) return 'midday'
  if (m < 18 * 60) return 'afternoon'
  return 'evening'
}

export function groupByBucket(departures) {
  const groups = Object.fromEntries(BUCKETS.map((b) => [b, []]))
  const sorted = [...departures].sort((a, b) => minutes(a.time) - minutes(b.time))
  for (const d of sorted) groups[bucketOf(d.time)].push(d)
  return groups
}

const taipeiClock = new Intl.DateTimeFormat('en-US', {
  timeZone: TAIPEI, weekday: 'short', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
})

/** The weekday ('Sat') and minutes since midnight of an instant, in Taipei. */
function taipeiNow(date) {
  const p = Object.fromEntries(taipeiClock.formatToParts(date).map((x) => [x.type, x.value]))
  return { weekday: p.weekday, minutes: Number(p.hour) * 60 + Number(p.minute) }
}

export function dayTypeOf(date) {
  const { weekday } = taipeiNow(date)
  return weekday === 'Sat' || weekday === 'Sun' ? 'holiday' : 'weekday'
}

export function nextDeparture(departures, now) {
  const today = dayTypeOf(now)
  const current = taipeiNow(now).minutes
  const candidates = departures
    .filter((d) => d.day_type === today && minutes(d.time) >= current)
    .sort((a, b) => minutes(a.time) - minutes(b.time))
  return candidates[0] ?? null
}

/** "*13:40" → irregular 13:40. The sheet's own notation, so typing it works. */
export function parseDepartureInput(text) {
  const match = /^\s*(\*)?\s*(\d{1,2}):(\d{2})\s*$/.exec(text)
  if (!match) return null
  const [, star, h, m] = match
  if (Number(h) > 23 || Number(m) > 59) return null
  return { time: `${h.padStart(2, '0')}:${m}`, irregular: Boolean(star) }
}

export function formatDeparture({ time, irregular }) {
  const [h, m] = time.split(':')
  return `${irregular ? '*' : ''}${Number(h)}:${m}`
}
