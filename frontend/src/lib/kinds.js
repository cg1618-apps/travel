/**
 * Kinds and usage, shared by packing lists and trips. Pure, so the shelf
 * rules the screens rely on are tested once.
 */

import { AUTO_SAVED_LABEL, KIND_LABELS, USAGE_LABELS } from './labels'
import { taipeiInputValue, tripEnd, tripStart } from './trips'

export const AUTO_SAVE_LIMIT = { lists: 5, trips: 10 }

const CURRENT = ['in_use', 'upcoming']

export const isAutoSaved = (row) => row.kind === 'free' && row.usage === 'past'

/** The badge beside a name: every kind but a plain 一般 one. */
export function badgeFor(row) {
  if (isAutoSaved(row)) return AUTO_SAVED_LABEL
  return row.kind === 'free' ? null : KIND_LABELS[row.kind]
}

/** A list's date at Taipei 00:00, ms; null when it has none. */
const taipeiMidnight = (day) => new Date(`${day}T00:00:00+08:00`).getTime()

/**
 * Where a row starts, ms, or null: a trip's earliest departure, a list's
 * effective 出發 date (the API's `departure_at`) at Taipei 00:00.
 */
export function rowStart(row) {
  if (Array.isArray(row.legs)) return tripStart(row)
  return row.departure_at ? taipeiMidnight(row.departure_at) : null
}

/**
 * 一般 rows that are 使用中 or 未來使用, soonest start first, a row with no
 * start after every row with one, ties in the order given. `startOf` is
 * `rowStart` on the screen; tests pass their own.
 *
 * `on_dashboard` in `app/services/domain/dashboard.py` is the same rule for
 * the sheet backup, pinned to the cases in kinds.test.js.
 */
export function onDashboard(rows, startOf = rowStart) {
  const current = rows.filter((row) => row.kind === 'free' && CURRENT.includes(row.usage))
  const keyed = current.map((row, index) => ({ row, index, start: startOf(row) }))
  keyed.sort((a, b) => {
    if (a.start !== b.start) {
      if (a.start === null) return 1
      if (b.start === null) return -1
      return a.start - b.start
    }
    return a.index - b.index
  })
  return keyed.map(({ row }) => row)
}

/** Packing list id to the leg it is linked from, over every trip given. */
export function legsByList(trips) {
  const map = new Map()
  for (const trip of trips) {
    for (const leg of trip.legs) if (leg.packing_list_id) map.set(leg.packing_list_id, leg)
  }
  return map
}

const DAY_MS = 86_400_000

/**
 * Where a row ends, ms, or null. A trip: its latest arrival (else departure).
 * A list linked from a leg with a time: that leg's arrival (else departure).
 * Any other list: the end of its 出發 day in Taipei.
 */
export function rowEnd(row, linkedLegs = new Map()) {
  if (Array.isArray(row.legs)) return tripEnd(row)
  const leg = linkedLegs.get(row.id)
  const legTime = leg && (leg.arrives_at ?? leg.departs_at)
  if (legTime) return new Date(legTime).getTime()
  return row.departure_at ? taipeiMidnight(row.departure_at) + DAY_MS : null
}

/** 已結束: the row's end has passed. No end, no badge. */
export function hasEnded(row, now, linkedLegs) {
  const end = rowEnd(row, linkedLegs)
  return end !== null && end < now.getTime()
}

/** Every row of an index response, each once. */
export function everyRow(index) {
  const seen = new Set()
  return [...index.free, ...index.auto_saved, ...index.saved, ...index.templates].filter((row) => {
    if (seen.has(row.id)) return false
    seen.add(row.id)
    return true
  })
}

// 當作範本 keeps the source's name, since the 範本 badge already says what it
// is. Templates named before that still carry the suffix, so a fill drops it.
const TEMPLATE_SUFFIX = '（範本）'

/** 使用中 and friends for a 一般 row; 保存 or 範本 for the others. */
export const statusLabel = (row) =>
  row.kind === 'free' ? USAGE_LABELS[row.usage] : KIND_LABELS[row.kind]

/** The index tabs, in the order they are shown. `shelf` is the API's array. */
export const TABS = [
  { key: 'free', label: KIND_LABELS.free, shelf: 'free' },
  { key: 'template', label: KIND_LABELS.template, shelf: 'templates' },
  { key: 'saved', label: KIND_LABELS.saved, shelf: 'saved' },
  { key: 'auto_saved', label: AUTO_SAVED_LABEL, shelf: 'auto_saved' },
]

/** `?tab=` to a tab key. Anything unknown - a stale bookmark - is 一般. */
export function tabFromSearch(value) {
  return TABS.some((tab) => tab.key === value) ? value : 'free'
}

/** The tab a row is listed on, for a link back to it. */
export const tabFor = (row) => (isAutoSaved(row) ? 'auto_saved' : row.kind)

/** What each tab shows beside its label; 自動保存 against its limit. */
export function tabCounts(index, limit) {
  return Object.fromEntries(
    TABS.map(({ key, shelf }) => [
      key,
      key === 'auto_saved' ? `${index[shelf].length} / ${limit}` : String(index[shelf].length),
    ]),
  )
}

/**
 * The name field after picking a source to create from. `fill` is what this
 * last wrote; a name that is neither empty nor that fill was typed by hand
 * and is kept.
 */
export function autofillName({ current, lastFill, source }) {
  const fill = source ? source.replace(new RegExp(`${TEMPLATE_SUFFIX}$`), '') : ''
  const untouched = current === '' || current === lastFill
  return { name: untouched ? fill : current, fill }
}

// Compared as instants, not strings: the offset the API writes depends on the
// database session's timezone.
const newestCreatedFirst = (a, b) =>
  new Date(b.created_at) - new Date(a.created_at) || b.id - a.id

/**
 * What a leg can link: every list but templates, newest created first. A
 * template the leg is already linked to stays, or the select would show
 * （不連結） for a leg that is linked.
 */
export function linkChoices(index, linkedId) {
  return everyRow(index)
    .filter((row) => row.kind !== 'template' || row.id === linkedId)
    .sort(newestCreatedFirst)
}

/**
 * `{name} ({date}) · {created date, Taipei} · {status}`, for the link picker.
 * `({date})` is the list's own 出發 date, as the list header writes it, and
 * only when it has one.
 */
export function linkLabel(row) {
  const name = row.departure_at ? `${row.name} (${row.departure_at})` : row.name
  return `${name} · ${taipeiInputValue(row.created_at).slice(0, 10)} · ${statusLabel(row)}`
}
