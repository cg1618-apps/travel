/**
 * The two lines under a list's name: when it leaves, and how far along it is.
 *
 * Pure so the day boundaries can be tested standing on them. `today` is a
 * parameter for the same reason `daysUntil` takes one.
 */

import { daysUntil } from './timing'

/** "3 天後出發 · 2026-10-03", plus where the date came from when not the list. */
export function leavingText(departureAt, source, today) {
  if (!departureAt) return '未設定日期'
  const days = daysUntil(departureAt, today)
  let text
  if (days === 0) text = `今天出發 · ${departureAt}`
  else if (days === 1) text = `明天出發 · ${departureAt}`
  else if (days < 0) text = `已出發 ${-days} 天 · ${departureAt}`
  else text = `${days} 天後出發 · ${departureAt}`
  return source === 'trip_leg' ? `${text} · 由 This time 行程設定` : text
}

/**
 * How far through the list you are, as the header's three pieces. Null for an
 * empty list, which has no progress to report.
 *
 * "Settled" is anything not 未打包: a 不需打包 item is as finished as a packed
 * one. Ready means every item settled and nothing waiting on a Double Check.
 */
export function progressParts(items) {
  if (items.length === 0) return null
  const settled = items.filter((item) => item.status !== 'not_packed').length
  const unchecked = items.filter(
    (item) => item.needs_double_check && !item.double_checked,
  ).length
  const ready = settled === items.length && unchecked === 0
  return {
    settled: `已處理 ${settled} / ${items.length}`,
    unchecked: unchecked > 0 ? ` · ${unchecked} 項待確認` : null,
    ready: ready ? ' · 可以出發了' : null,
  }
}
