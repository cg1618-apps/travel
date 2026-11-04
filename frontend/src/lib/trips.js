/**
 * Leg times. Stored as instants; always shown and entered in Asia/Taipei,
 * whatever timezone the viewing device is in.
 */

import { DONE_LABEL, NOT_DONE_LABEL, TICKET_STATUS_LABELS } from './labels'
import { untickedLabels } from './legTypes'

export const TAIPEI = 'Asia/Taipei'

/** "2h53m"; null when either end is unset, since a half-known leg has no length. */
export function formatDuration(departsAt, arrivesAt) {
  if (!departsAt || !arrivesAt) return null
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
  if (!departsAt) return formatTaipei(arrivesAt)
  return taipeiDay(departsAt) === taipeiDay(arrivesAt)
    ? taipeiInputValue(arrivesAt).slice(11)
    : formatTaipei(arrivesAt)
}

/**
 * A leg's times on one line, coping with either being unset:
 * "Thu 09/24 18:06 – 20:59 · 2h53m", "Thu 09/24 18:06" when only the departure
 * is known or the two are the same instant, "– Thu 09/24 20:59" when only the
 * arrival is. Null when neither is set.
 */
export function formatLegTimes({ departs_at: departs, arrives_at: arrives }) {
  if (!departs && !arrives) return null
  if (!departs) return `– ${formatTaipei(arrives)}`
  if (!arrives || new Date(arrives).getTime() === new Date(departs).getTime()) {
    return formatTaipei(departs)
  }
  return `${formatTaipei(departs)} – ${formatArrival(departs, arrives)} · ${formatDuration(departs, arrives)}`
}

const ms = (iso) => new Date(iso).getTime()
const legStart = (leg) => leg.departs_at ?? leg.arrives_at ?? null
const legEnd = (leg) => leg.arrives_at ?? leg.departs_at ?? null

/** Earliest of the given instants, as ms; null when none is set. */
function earliest(values) {
  const set = values.filter(Boolean).map(ms)
  return set.length ? Math.min(...set) : null
}

function latest(values) {
  const set = values.filter(Boolean).map(ms)
  return set.length ? Math.max(...set) : null
}

/**
 * "09/24" for a trip's first day, "09/24 – 09/28" across days; null when no
 * leg has a time. A leg with one time counts that time as both its ends.
 */
export function tripDateRange(legs) {
  const first = earliest(legs.map(legStart))
  const last = latest(legs.map(legEnd))
  if (first === null) return null
  const short = (instant) => taipeiDay(new Date(instant).toISOString()).slice(5).replace('-', '/')
  const start = short(first)
  const end = short(last)
  return start === end ? start : `${start} – ${end}`
}

/** A trip's start, for the dashboard's order: its earliest departure, ms, or null. */
export const tripStart = (trip) => earliest(trip.legs.map((leg) => leg.departs_at))

/** A trip's end, for 已結束: its latest arrival, else departure, ms, or null. */
export const tripEnd = (trip) => latest(trip.legs.map(legEnd))

/** The earliest departure as an instant string, or null: what a copy starts from. */
export function firstDeparture(legs) {
  const first = earliest(legs.map((leg) => leg.departs_at))
  return first === null ? null : new Date(first).toISOString()
}

/**
 * Legs in the order they happen: by departure, a leg with none after every
 * leg with one, then by id - the server's own order.
 */
export function sortLegs(legs) {
  const key = (leg) => (leg.departs_at ? ms(leg.departs_at) : Infinity)
  return [...legs].sort((a, b) => {
    const ka = key(a)
    const kb = key(b)
    if (ka !== kb) return ka < kb ? -1 : 1
    return a.id - b.id
  })
}

/** A copy needs a start date only when some leg has a time to move. */
export function needsStartDate(trip) {
  return trip.legs.some((leg) => leg.departs_at)
}

/**
 * The arrival field after the departure is changed: an empty arrival takes
 * the departure, as the server does on save; a set one is left alone.
 */
export const fillArrival = (departs, arrives) => (arrives ? arrives : departs)

/**
 * Whether a trip may be marked 已準備完成, and what is missing: tickets not
 * bought, and how many legs show a tick that is not ticked. The server decides
 * the same and refuses `done: true` otherwise (`trip_readiness` there).
 */
export function tripReadiness(trip) {
  const ticketsMissing = trip.ticket_status === 'not_bought'
  const untickedLegs = trip.legs.filter((leg) => untickedLabels(leg).length > 0).length
  return { ready: !ticketsMissing && untickedLegs === 0, ticketsMissing, untickedLegs }
}

/** Why 已準備完成 cannot be ticked yet, in a few words; null when it can. */
export function readinessHint({ ready, ticketsMissing, untickedLegs }) {
  if (ready) return null
  const parts = []
  if (ticketsMissing) parts.push('未買票')
  if (untickedLegs) parts.push('還有未完成的標籤')
  return parts.join('、')
}

/**
 * The badges a trip carries on the dashboard and the 行程 index: 已準備完成
 * or 未準備完成, then 已買票 or 未買票 (nothing for 無需買票). A 範本 has
 * none - it is only a starting point.
 */
export function readinessBadges(trip) {
  if (trip.kind === 'template') return []
  const badges = [trip.done ? DONE_LABEL : NOT_DONE_LABEL]
  if (trip.ticket_status !== 'not_needed') badges.push(TICKET_STATUS_LABELS[trip.ticket_status])
  return badges.filter(Boolean)
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

/**
 * One compact line for a leg on the 行程 index: route, departure, duration,
 * 車種. A leg with no departure shows its arrival instead, and one with
 * neither shows only the route.
 */
export function legSummary(leg) {
  const parts = [`${leg.from_place} → ${leg.to_place}`]
  if (leg.departs_at) parts.push(formatTaipei(leg.departs_at))
  else if (leg.arrives_at) parts.push(`抵達 ${formatTaipei(leg.arrives_at)}`)
  const duration = formatDuration(leg.departs_at, leg.arrives_at)
  if (duration && duration !== '0m') parts.push(duration)
  if (leg.service?.trim()) parts.push(leg.service.trim())
  return parts.join(' · ')
}
