/**
 * The 選項 screen's tabs: one per label kind, in `LABEL_KIND_LABELS` order.
 *
 * The tab lives in `?tab=` the way the index tabs' does (`tabFromSearch` in
 * `kinds.js`); the first kind, 類別, is the bare URL.
 */

import { LABEL_KIND_LABELS } from './labels'

export const OPTION_KINDS = Object.keys(LABEL_KIND_LABELS)

/** `?tab=` to a kind. Anything unknown - a stale bookmark - is the first. */
export function kindFromSearch(value) {
  return OPTION_KINDS.includes(value) ? value : OPTION_KINDS[0]
}

/** The search params that select `kind`: none for the first. */
export const searchForKind = (kind) => (kind === OPTION_KINDS[0] ? {} : { tab: kind })

/** How many remembered values each kind holds; a kind with none is 0. */
export function optionCounts(options) {
  const counts = Object.fromEntries(OPTION_KINDS.map((kind) => [kind, 0]))
  for (const option of options) {
    if (option.kind in counts) counts[option.kind] += 1
  }
  return counts
}
