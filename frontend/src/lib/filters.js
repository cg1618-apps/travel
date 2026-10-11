/**
 * The sheet's column filters: 打包狀態, Double Check, 打包時機, 需求 and
 * 取得地點, Google Sheets' "filter by values".
 *
 * A filter is the set of values a column may show; an empty set means the
 * column is not filtered. Columns combine with AND, values within a column
 * with OR. An unset 需求 or 取得地點 is the value '' so it can be picked too.
 *
 * Beside the columns sits one flag, `unfinished`: the toolbar's 未完成, a row
 * that is 未打包 or 未確認. It spans two columns with OR, which no column filter
 * can say, so it is its own key, ANDed with the columns like any of them.
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

/** 未完成: still to pack, or still to double-check. */
export const isUnfinished = (item) => item.status === 'not_packed' || checkState(item) === 'needed'

const activeColumns = (filters) =>
  Object.entries(filters).filter(([key, selected]) => key in FILTERS && selected?.length)

export const isFiltering = (filters) => Boolean(filters.unfinished) || activeColumns(filters).length > 0

export function applyFilters(items, filters) {
  const active = activeColumns(filters)
  if (!filters.unfinished && active.length === 0) return items
  return items.filter(
    (item) =>
      (!filters.unfinished || isUnfinished(item)) &&
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
 * The toolbar's 未打包 / 未完成 / 全部 switch. 未打包 and 全部 are read off the
 * 打包狀態 filter rather than kept beside it, so the header and the switch
 * cannot disagree, and any other choice made in the header is neither.
 * 未完成 is the `unfinished` flag, and wins while it is on: it is the one
 * filter the headers cannot show.
 */
export function statusScope(filters) {
  if (filters.unfinished) return 'unfinished'
  const selected = filters.status ?? []
  if (selected.length === 0) return 'all'
  if (selected.length === 1 && selected[0] === 'not_packed') return 'not_packed'
  return null
}

export function withStatusScope(filters, scope) {
  const { unfinished: _, ...rest } = filters
  const next = { ...rest, status: scope === 'not_packed' ? ['not_packed'] : [] }
  return scope === 'unfinished' ? { ...next, unfinished: true } : next
}
