/**
 * Kinds and usage, shared by packing lists and trips. Pure, so the shelf
 * rules the screens rely on are tested once.
 */

import { AUTO_SAVED_LABEL, KIND_LABELS, USAGE_LABELS } from './labels'
import { taipeiInputValue } from './trips'

export const AUTO_SAVE_LIMIT = { lists: 5, trips: 10 }

const CURRENT = ['in_use', 'upcoming']

export const isAutoSaved = (row) => row.kind === 'free' && row.usage === 'past'

/** The badge beside a name: every kind but a plain 一般 one. */
export function badgeFor(row) {
  if (isAutoSaved(row)) return AUTO_SAVED_LABEL
  return row.kind === 'free' ? null : KIND_LABELS[row.kind]
}

/** 一般 rows that are 使用中 or 未來使用, 使用中 first, order otherwise kept. */
export function onDashboard(rows) {
  const current = rows.filter((row) => row.kind === 'free' && CURRENT.includes(row.usage))
  return [
    ...current.filter((row) => row.usage === 'in_use'),
    ...current.filter((row) => row.usage === 'upcoming'),
  ]
}

/** Every row of an index response, each once. */
export function everyRow(index) {
  const seen = new Set()
  return [...index.free, ...index.auto_saved, ...index.saved, ...index.templates].filter((row) =>
    seen.has(row.id) ? false : seen.add(row.id),
  )
}

const TEMPLATE_SUFFIX = '（範本）'

export const templateName = (name) => `${name}${TEMPLATE_SUFFIX}`

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

/** `{name} · {created date, Taipei} · {status}`, for the link picker. */
export const linkLabel = (row) =>
  `${row.name} · ${taipeiInputValue(row.created_at).slice(0, 10)} · ${statusLabel(row)}`
