/**
 * When each group of items is due, computed from the list's departure date.
 *
 * This lives on the frontend because the viewer's calendar day is the one that
 * matters and the server's is not necessarily the same one. That makes it a
 * date boundary — the piece of logic most likely to be wrong and least likely
 * to be noticed, since it is only wrong on the evening it counts.
 *
 * `today` is a parameter rather than a call to `new Date()` inside, so the
 * tests can stand on a boundary instead of waiting for one.
 */

/** The four timings, in the order the list renders them. */
export const TIMINGS = ['whenever', 'night_before', 'day_of', 'just_before']

export const TIMING_LABELS = {
  whenever: 'Whenever',
  night_before: 'The night before',
  day_of: 'The day of',
  just_before: 'Just before leaving',
}

/**
 * Parse a YYYY-MM-DD date into a UTC midnight timestamp.
 *
 * Deliberately not `new Date(string)` on a full ISO timestamp: a bare
 * YYYY-MM-DD is parsed as UTC while YYYY-MM-DDTHH:mm is parsed as local, so
 * mixing the two shifts dates by a day for anyone east or west of Greenwich.
 * Splitting the parts sidesteps the question entirely.
 */
function toUtcDay(value) {
  if (!value) return null
  if (value instanceof Date) {
    return Date.UTC(value.getFullYear(), value.getMonth(), value.getDate())
  }
  const [year, month, day] = String(value).slice(0, 10).split('-').map(Number)
  if (!year || !month || !day) return null
  return Date.UTC(year, month - 1, day)
}

const DAY = 24 * 60 * 60 * 1000

/**
 * Whole days from `today` until `departureAt`. Negative once it has passed.
 * Returns null when either date is missing.
 */
export function daysUntil(departureAt, today) {
  const from = toUtcDay(today)
  const to = toUtcDay(departureAt)
  if (from === null || to === null) return null
  return Math.round((to - from) / DAY)
}

/**
 * The timings that are due now, as a Set.
 *
 * With no departure date nothing is due except `whenever`, and the screen
 * highlights nothing. A list without a date is normal, not incomplete.
 */
export function dueTimings(departureAt, today) {
  const due = new Set(['whenever'])
  const days = daysUntil(departureAt, today)
  if (days === null) return due

  if (days <= 1) due.add('night_before')
  if (days <= 0) {
    due.add('day_of')
    due.add('just_before')
  }
  return due
}

/** Whether a whole list has anything outstanding. */
export function isTimingDue(timing, departureAt, today) {
  return dueTimings(departureAt, today).has(timing)
}
