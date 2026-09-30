/**
 * Departure times: the sheet's 早/中/下午/晚 columns, computed from the clock.
 *
 * `now` is always a parameter, never a `new Date()` inside, so tests can stand
 * on a boundary. Weekday vs holiday is Monday–Friday vs Saturday–Sunday;
 * public holidays are not modelled.
 */

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

export function dayTypeOf(date) {
  const day = date.getDay()
  return day === 0 || day === 6 ? 'holiday' : 'weekday'
}

export function nextDeparture(departures, now) {
  const today = dayTypeOf(now)
  const current = now.getHours() * 60 + now.getMinutes()
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
