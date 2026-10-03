/**
 * New rows on the sheet before they are saved: every column filled in where
 * it sits, as in a spreadsheet, then one 儲存 for all of them.
 *
 * Kept client-side until the save so a row lands in its 類別 complete,
 * instead of jumping into its group the moment the category is typed and
 * leaving the rest of it to be chased down the sheet.
 */

import { CHECK_FIELDS } from './labels'
import { parseWholeNumber } from './numbers'

let nextKey = 0

export function emptyDraft(category = '') {
  nextKey += 1
  return {
    key: `draft-${nextKey}`,
    category,
    name: '',
    detail: '',
    quantity: '',
    unit: '',
    quantity_packed: '',
    status: 'not_packed',
    check: 'off',
    timing: 'whenever',
    need: '',
    location: '',
    notes: '',
  }
}

const TYPED = ['category', 'name', 'detail', 'quantity', 'unit', 'quantity_packed', 'location', 'notes']

/** Nothing typed and every choice left at its default: skipped, not refused. */
export function isBlank(draft) {
  const fresh = emptyDraft()
  return (
    TYPED.every((field) => !draft[field].trim()) &&
    ['status', 'check', 'timing', 'need'].every((field) => draft[field] === fresh[field])
  )
}

/** Which fields stop this row from saving, by field name. */
export function draftProblems(draft) {
  const problems = []
  if (!draft.name.trim()) problems.push('name')
  if (parseWholeNumber(draft.quantity) === undefined) problems.push('quantity')
  if (parseWholeNumber(draft.quantity_packed) === undefined) problems.push('quantity_packed')
  return problems
}

const textOrNull = (text) => text.trim() || null

/** The API's create body for one row. Call only on a row with no problems. */
export function toPayload(draft) {
  return {
    name: draft.name.trim(),
    detail: textOrNull(draft.detail),
    category: textOrNull(draft.category),
    location: textOrNull(draft.location),
    need: draft.need || null,
    quantity: parseWholeNumber(draft.quantity),
    unit: textOrNull(draft.unit),
    quantity_packed: parseWholeNumber(draft.quantity_packed),
    status: draft.status,
    timing: draft.timing,
    ...CHECK_FIELDS[draft.check],
    notes: textOrNull(draft.notes),
  }
}
