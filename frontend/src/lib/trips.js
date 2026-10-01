/**
 * Leg times. Stored as instants; always shown and entered in Asia/Taipei,
 * whatever timezone the viewing device is in.
 */

export const TAIPEI = 'Asia/Taipei'

export function formatDuration(departsAt, arrivesAt) {
  const total = Math.round((new Date(arrivesAt) - new Date(departsAt)) / 60000)
  const h = Math.floor(total / 60)
  const m = total % 60
  return h ? `${h}h${String(m).padStart(2, '0')}m` : `${m}m`
}

function parts(iso) {
  const fmt = new Intl.DateTimeFormat('en-US', {
    timeZone: TAIPEI, weekday: 'short', year: 'numeric', month: '2-digit',
    day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  })
  return Object.fromEntries(fmt.formatToParts(new Date(iso)).map((p) => [p.type, p.value]))
}

export function formatTaipei(iso) {
  const p = parts(iso)
  return `${p.weekday} ${p.month}/${p.day} ${p.hour}:${p.minute}`
}

export function taipeiInputValue(iso) {
  const p = parts(iso)
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`
}

/** Taiwan has no daylight saving, so the offset is always +08:00. */
export function fromTaipeiInput(value) {
  return `${value}:00+08:00`
}

function taipeiDay(iso) {
  return taipeiInputValue(iso).slice(0, 10)
}

/** The arrival under a leg's departure: the clock alone when it is the same Taipei day. */
export function formatArrival(departsAt, arrivesAt) {
  return taipeiDay(departsAt) === taipeiDay(arrivesAt)
    ? taipeiInputValue(arrivesAt).slice(11)
    : formatTaipei(arrivesAt)
}

/** "09/24" for a trip's first day, "09/24 – 09/28" across days; null with no legs. */
export function tripDateRange(legs) {
  if (legs.length === 0) return null
  const first = legs.reduce((a, b) => (new Date(b.departs_at) < new Date(a.departs_at) ? b : a))
  const last = legs.reduce((a, b) => (new Date(b.arrives_at) > new Date(a.arrives_at) ? b : a))
  const short = (iso) => taipeiDay(iso).slice(5).replace('-', '/')
  const start = short(first.departs_at)
  const end = short(last.arrives_at)
  return start === end ? start : `${start} – ${end}`
}

/** Legs in the order they happen. */
export function sortLegs(legs) {
  return [...legs].sort((a, b) => new Date(a.departs_at) - new Date(b.departs_at))
}

/** A copy needs a start date only when there are legs to move. */
export function needsStartDate(trip) {
  return trip.legs.length > 0
}

/** One line per template leg whose packing list the copy did not carry. */
export function unlinkedNotice({ from_place: from, to_place: to, packing_list_name: list }) {
  return `「${from} → ${to}」在範本中連結了「${list}」，請自行連結打包清單。`
}

/** The first line with anything on it, for a one-line preview; null when none. */
export function firstLine(text) {
  if (!text) return null
  return text.split('\n').find((line) => line.trim()) ?? null
}
