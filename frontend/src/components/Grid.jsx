/**
 * The packing list as a sheet: one row per thing, one column per fact.
 *
 * This is the view the app is planned in. It replaced a screen that grouped
 * items by a mode you had to pick from "When / Category / Bag" — internal
 * vocabulary from the data model, put on screen as a question. A sheet asks
 * nothing: every column is visible, every header sorts, every cell edits where
 * it sits.
 */

import { useState } from 'react'

import { TIMINGS, TIMING_LABELS } from '../lib/timing'
import { QuantityCell, SelectCell, TextCell } from './Cell'

const STATUS_ORDER = ['not_packed', 'packed', 'no_need']
const NEXT_STATUS = { not_packed: 'packed', packed: 'no_need', no_need: 'not_packed' }
const STATUS_MARK = { not_packed: '☐', packed: '☑', no_need: '—' }
const STATUS_TITLE = {
  not_packed: 'Not packed — click to tick',
  packed: 'Packed — click for "no need"',
  no_need: 'No need — click to reset',
}

// Three states in one control: off, needed, done. It maps onto the two
// underlying fields, and having one thing to click makes "packed but not yet
// verified" a state you can see rather than one you have to reason about.
const NEXT_CHECK = {
  off: { needs_double_check: true, double_checked: false },
  needed: { needs_double_check: true, double_checked: true },
  done: { needs_double_check: false, double_checked: false },
}
const CHECK_MARK = { off: '·', needed: '⚠', done: '✓' }
const CHECK_TITLE = {
  off: 'No check needed — click to flag',
  needed: 'Needs checking — click when done',
  done: 'Checked — click to clear',
}

function checkState(item) {
  if (!item.needs_double_check) return 'off'
  return item.double_checked ? 'done' : 'needed'
}

const COLUMNS = [
  { key: 'name', label: 'Item', width: 'w-[24%]', sortable: true },
  { key: 'quantity', label: 'Qty', width: 'w-32', sortable: true },
  { key: 'bag', label: 'Bag', width: 'w-32', sortable: true },
  { key: 'category', label: 'Category', width: 'w-32', sortable: true },
  { key: 'timing', label: 'When', width: 'w-32', sortable: true },
  { key: 'check', label: 'Check', width: 'w-16', sortable: false },
  { key: 'notes', label: 'Notes', width: 'w-44', sortable: false },
  { key: 'status', label: '✓', width: 'w-12', sortable: true },
]

function sortValue(item, key) {
  if (key === 'status') return STATUS_ORDER.indexOf(item.status)
  if (key === 'timing') return TIMINGS.indexOf(item.timing)
  if (key === 'quantity') return item.quantity ?? -1
  return (item[key] || '').toLowerCase()
}

export function Grid({ items, categories, bags, onPatch, onDelete, onAdd }) {
  // Null means "the order they were added", which is the sheet's own order and
  // the one people expect back when they stop sorting.
  const [sort, setSort] = useState(null)
  const [adding, setAdding] = useState('')

  const rows = sort
    ? [...items].sort((a, b) => {
        const left = sortValue(a, sort.key)
        const right = sortValue(b, sort.key)
        if (left === right) return a.position - b.position
        return (left > right ? 1 : -1) * (sort.direction === 'asc' ? 1 : -1)
      })
    : items

  const toggleSort = (key) =>
    setSort((current) => {
      if (current?.key !== key) return { key, direction: 'asc' }
      if (current.direction === 'asc') return { key, direction: 'desc' }
      return null
    })

  const submitNew = (event) => {
    event.preventDefault()
    if (!adding.trim()) return
    onAdd(adding.trim())
    setAdding('')
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] border-collapse text-sm whitespace-nowrap">
        <thead>
          <tr className="border-y border-border bg-surface-2">
            {COLUMNS.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={`${column.width} border-r border-border px-2 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-muted last:border-r-0`}
              >
                {column.sortable ? (
                  <button
                    type="button"
                    onClick={() => toggleSort(column.key)}
                    className="flex w-full items-center gap-1 text-left uppercase"
                    style={{ minHeight: 0 }}
                  >
                    {column.label}
                    <span aria-hidden="true" className="text-text-faint">
                      {sort?.key === column.key
                        ? sort.direction === 'asc'
                          ? '▲'
                          : '▼'
                        : '▾'}
                    </span>
                  </button>
                ) : (
                  column.label
                )}
              </th>
            ))}
            <th scope="col" className="w-10" />
          </tr>
        </thead>

        <tbody>
          {rows.map((item) => (
            <tr
              key={item.id}
              className={`border-b border-border ${
                item.status === 'no_need' ? 'text-text-faint' : ''
              }`}
            >
              <td className="border-r border-border">
                <TextCell
                  value={item.name}
                  placeholder="(unnamed)"
                  onCommit={(name) => name && onPatch(item.id, { name })}
                />
              </td>
              <td className="border-r border-border">
                <QuantityCell item={item} onCommit={(changes) => onPatch(item.id, changes)} />
              </td>
              <td className="border-r border-border">
                <TextCell
                  value={item.bag}
                  placeholder="—"
                  options={bags}
                  listId="bag-options"
                  onCommit={(bag) => onPatch(item.id, { bag })}
                />
              </td>
              <td className="border-r border-border">
                <TextCell
                  value={item.category}
                  placeholder="—"
                  options={categories}
                  listId="category-options"
                  onCommit={(category) => onPatch(item.id, { category })}
                />
              </td>
              <td className="border-r border-border">
                <SelectCell
                  value={item.timing}
                  options={TIMINGS}
                  labels={TIMING_LABELS}
                  onCommit={(timing) => onPatch(item.id, { timing })}
                />
              </td>
              <td className="border-r border-border text-center">
                <button
                  type="button"
                  onClick={() => onPatch(item.id, NEXT_CHECK[checkState(item)])}
                  title={CHECK_TITLE[checkState(item)]}
                  aria-label={`${item.name}: ${CHECK_TITLE[checkState(item)]}`}
                  className={`w-full px-2 py-1.5 ${
                    checkState(item) === 'needed'
                      ? 'text-warning'
                      : checkState(item) === 'done'
                        ? 'text-success'
                        : 'text-text-faint'
                  }`}
                  style={{ minHeight: 0 }}
                >
                  {CHECK_MARK[checkState(item)]}
                </button>
              </td>
              <td className="border-r border-border">
                <TextCell
                  value={item.notes}
                  placeholder="—"
                  onCommit={(notes) => onPatch(item.id, { notes })}
                />
              </td>
              <td className="border-r border-border text-center">
                <button
                  type="button"
                  onClick={() => onPatch(item.id, { status: NEXT_STATUS[item.status] })}
                  title={STATUS_TITLE[item.status]}
                  aria-label={`${item.name}: ${STATUS_TITLE[item.status]}`}
                  className={`w-full px-2 py-1.5 text-base ${
                    item.status === 'packed' ? 'text-brand' : 'text-text-faint'
                  }`}
                  style={{ minHeight: 0 }}
                >
                  {STATUS_MARK[item.status]}
                </button>
              </td>
              <td className="text-center">
                <button
                  type="button"
                  onClick={() => onDelete(item.id)}
                  aria-label={`Delete ${item.name}`}
                  className="px-2 py-1.5 text-text-faint hover:text-danger"
                  style={{ minHeight: 0 }}
                >
                  ✕
                </button>
              </td>
            </tr>
          ))}

          <tr>
            <td colSpan={COLUMNS.length + 1} className="border-b border-border">
              <form onSubmit={submitNew}>
                <input
                  value={adding}
                  onChange={(event) => setAdding(event.target.value)}
                  placeholder="▸ add row…"
                  aria-label="Add a row"
                  className="w-full bg-transparent px-2 py-2 text-sm outline-none placeholder:text-text-faint focus:bg-brand-soft"
                />
              </form>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}
