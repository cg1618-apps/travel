/**
 * What a row's ⋯ menu (or a long-press) offers, in both views.
 *
 * One builder so the sheet and the checklist cannot drift. 不需打包 lives
 * here rather than on the tap, because it is a decision about the list and a
 * tap is progress through it.
 */

import { CHECK_FIELDS, CHECK_LABELS, CHECK_STATES, checkState } from './labels'

/** An item as a person names it: "鑰匙 · 家鑰匙". */
export function itemTitle(item) {
  return item.detail ? `${item.name} · ${item.detail}` : item.name
}

/** `onDelete` gets the whole row, so the confirmation can name it. */
export function rowActions(item, { onPatch, onAddVariant, onDelete, withChecks = false }) {
  const actions = [
    item.status === 'no_need'
      ? { label: '改回未打包', onSelect: () => onPatch(item.id, { status: 'not_packed' }) }
      : { label: '設為不需打包', onSelect: () => onPatch(item.id, { status: 'no_need' }) },
    { label: '新增變化', onSelect: () => onAddVariant(item) },
  ]
  if (withChecks) {
    const current = checkState(item)
    for (const state of CHECK_STATES) {
      actions.push({
        label: `Double Check：${CHECK_LABELS[state]}${state === current ? ' ✓' : ''}`,
        onSelect: () => onPatch(item.id, CHECK_FIELDS[state]),
      })
    }
  }
  actions.push({ label: '刪除', danger: true, onSelect: () => onDelete(item) })
  return actions
}
