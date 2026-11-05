/**
 * 排序類別 (a list's 類別) or 排序群組 (transport routes): the order of the
 * groups, in a dialog of its own. `title`, `hint` and `nameOf` say which;
 * the defaults are a packing list's.
 *
 * Rows are dragged on the sheet; groups are dragged here. Doing both on one
 * surface would leave every drag asking which of the two it is. Nothing is
 * saved until 儲存, so a dialog closed half-way changes nothing.
 */

import { useState } from 'react'

import { DragHandle, SortableItem, SortableList } from './Sortable'

export const UNCATEGORISED = '（未分類）'

const categoryOf = (group) => group.category ?? UNCATEGORISED

export function GroupOrderDialog({
  groups,
  onSave,
  onCancel,
  title = '排序類別',
  hint = '拖曳類別調整順序，類別裡的項目會一起移動。',
  nameOf = categoryOf,
}) {
  const [order, setOrder] = useState(groups)
  const ids = order.map((group) => group.key)

  const move = (from, to) =>
    setOrder((current) => {
      const next = [...current]
      const [moved] = next.splice(from, 1)
      next.splice(to, 0, moved)
      return next
    })

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-ink/50 p-0 sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="group-order-title"
    >
      <div className="flex max-h-[85dvh] w-full max-w-md flex-col rounded-t-2xl border border-border bg-surface p-5 sm:rounded-2xl">
        <h2 id="group-order-title" className="m-0 text-base font-semibold">
          {title}
        </h2>
        <p className="mt-1 mb-3 text-sm text-text-muted">{hint}</p>

        <ul className="m-0 min-h-0 flex-1 list-none overflow-y-auto border-y border-border p-0">
          <SortableList ids={ids} onMove={move}>
            {order.map((group) => (
              <SortableItem
                key={group.key}
                id={group.key}
                as="li"
                className="flex items-center gap-2 border-b border-border px-2 py-2 last:border-b-0"
              >
                <DragHandle label={nameOf(group)} className="px-2 text-lg" />
                <span className={group.category === null ? 'text-text-faint' : ''}>
                  {nameOf(group)}
                </span>
                <span className="ml-auto text-xs text-text-faint tabular-nums">
                  {group.items.length} 項
                </span>
              </SortableItem>
            ))}
          </SortableList>
        </ul>

        <div className="mt-4 flex flex-col gap-2">
          <button
            type="button"
            onClick={() => onSave(order)}
            className="rounded-md bg-brand px-4 font-medium text-on-brand"
          >
            儲存
          </button>
          <button type="button" onClick={onCancel} className="px-4 text-text-muted">
            取消
          </button>
        </div>
      </div>
    </div>
  )
}
