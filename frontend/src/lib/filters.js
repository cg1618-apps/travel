/**
 * The sheet's column filters: 打包狀態, Double Check, 打包時機, 需求 and
 * 取得地點, Google Sheets' "filter by values".
 *
 * A filter is the set of values a column may show; an empty set means the
 * column is not filtered. Columns combine with AND, values within a column
 * with OR. An unset 需求 or 取得地點 is the value '' so it can be picked too.
 */

import { CHECK_LABELS, CHECK_STATES, NEED_LABELS, NEEDS, STATUS_LABELS, TIMING_LABELS, checkState } from './labels'
import { TIMINGS } from './timing'

const STATUSES = ['not_packed', 'packed', 'no_need']
export const BLANK_LABEL = '（空白）'

/** What each filterable column reads off an item, and the values it offers. */
export const FILTERS = {
  status: {
    read: (item) => item.status,
    values: () => STATUSES,
    label: (value) => STATUS_LABELS[value],
  },
  check: {
    read: checkState,
    values: () => CHECK_STATES,
    label: (value) => CHECK_LABELS[value],
  },
  timing: {
    read: (item) => item.timing,
    values: () => TIMINGS,
    label: (value) => TIMING_LABELS[value],
  },
  need: {
    read: (item) => item.need ?? '',
    values: () => [...NEEDS, ''],
    label: (value) => NEED_LABELS[value] ?? BLANK_LABEL,
  },
  location: {
    read: (item) => item.location ?? '',
    // Open vocabulary: only what the list actually holds, blanks last.
    values: (items) => {
      const present = new Set(items.map((item) => item.location ?? ''))
      const named = [...present].filter(Boolean).sort((a, b) => a.localeCompare(b, 'zh-Hant'))
      return present.has('') ? [...named, ''] : named
    },
    label: (value) => value || BLANK_LABEL,
  },
}

export const isFiltering = (filters) =>
  Object.values(filters).some((selected) => selected && selected.length > 0)

export function applyFilters(items, filters) {
  const active = Object.entries(filters).filter(([, selected]) => selected?.length)
  if (active.length === 0) return items
  return items.filter((item) =>
    active.every(([key, selected]) => selected.includes(FILTERS[key].read(item))),
  )
}

/** Adds or removes one value from a column's filter. */
export function toggleValue(filters, key, value) {
  const current = filters[key] ?? []
  const next = current.includes(value)
    ? current.filter((each) => each !== value)
    : [...current, value]
  return { ...filters, [key]: next }
}

/**
 * The toolbar's 未打包 / 全部 switch, read off the 打包狀態 filter rather than
 * kept beside it, so the header and the switch cannot disagree. Any other
 * choice made in the header is neither.
 */
export function statusScope(filters) {
  const selected = filters.status ?? []
  if (selected.length === 0) return 'all'
  if (selected.length === 1 && selected[0] === 'not_packed') return 'not_packed'
  return null
}

export const withStatusScope = (filters, scope) => ({
  ...filters,
  status: scope === 'not_packed' ? ['not_packed'] : [],
})
