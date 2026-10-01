/**
 * Kinds and usage, shared by packing lists and trips. Pure, so the shelf
 * rules the screens rely on are tested once.
 */

import { AUTO_SAVED_LABEL, KIND_LABELS } from './labels'

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
  return [...index.free, ...index.auto_saved, ...index.saved, ...index.templates].filter((row) => {
    if (seen.has(row.id)) return false
    seen.add(row.id)
    return true
  })
}

export const templateName = (name) => `${name}（範本）`

/**
 * Whether a PATCH may take the trip on /trip out of being current. Any usage
 * change counts, not only one out of 使用中 / 未來使用: 使用中 -> 未來使用 hands
 * /trip to another 使用中 trip, which would then appear under the click.
 */
export const leavesCurrent = (changes) => changes.kind === 'saved' || 'usage' in changes
