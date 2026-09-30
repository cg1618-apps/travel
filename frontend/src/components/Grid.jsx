/**
 * The packing list as a sheet: one row per thing, one column per fact.
 *
 * This is the view the app is planned in, and it reads like the owner's Google
 * Sheet — the same columns in the same order, in the sheet's own words. Every
 * header sorts, every cell edits where it sits. A single row lives in
 * `GridRow.jsx`.
 *
 * Under the list's own order a category or a name is written once per run and
 * left blank beneath, as in the sheet, so an item and its variants read as one
 * block. Any other sort turns that off: a blank cell under a foreign order
 * would be ambiguous.
 */

import { useState } from 'react'

import { CHECK_STATES, NEEDS, checkState } from '../lib/labels'
import { groupRuns } from '../lib/grouping'
import { TIMINGS } from '../lib/timing'
import { GridRow } from './GridRow'

const STATUS_ORDER = ['not_packed', 'packed', 'no_need']

// `bag` is not a column: the sheet has none. It stays in the data.
const COLUMNS = [
  { key: 'category', label: '類別', width: 'w-28' },
  { key: 'name', label: '項目', span: 2 },
  { key: 'quantity', label: '數量', width: 'w-24' },
  { key: 'quantity_packed', label: '已打包數量', width: 'w-24' },
  { key: 'status', label: '打包狀態', width: 'w-28' },
  { key: 'check', label: 'Double Check', width: 'w-28' },
  { key: 'timing', label: '打包時機', width: 'w-28' },
  { key: 'need', label: '需求', width: 'w-20' },
  { key: 'location', label: '取得地點', width: 'w-28' },
  { key: 'notes', label: '備註', width: 'w-44', sortable: false },
]
const CELL_COUNT = COLUMNS.reduce((sum, column) => sum + (column.span ?? 1), 0) + 1

function sortValue(item, key) {
  switch (key) {
    case 'status':
      return STATUS_ORDER.indexOf(item.status)
    case 'timing':
      return TIMINGS.indexOf(item.timing)
    case 'need':
      return NEEDS.indexOf(item.need)
    case 'check':
      return CHECK_STATES.indexOf(checkState(item))
    case 'quantity':
    case 'quantity_packed':
      return item[key] ?? -1
    case 'name':
      return `${item.name} ${item.detail ?? ''}`.toLowerCase()
    default:
      return (item[key] || '').toLowerCase()
  }
}

function SortHeader({ column, sort, onSort }) {
  if (column.sortable === false) return column.label
  const mark = sort?.key === column.key ? (sort.direction === 'asc' ? '▲' : '▼') : '▾'
  return (
    <button
      type="button"
      onClick={() => onSort(column.key)}
      className="flex w-full items-center gap-1 text-left"
      style={{ minHeight: 0 }}
    >
      {column.label}
      <span aria-hidden="true" className="text-text-faint">
        {mark}
      </span>
    </button>
  )
}

export function Grid({ items, categories, locations, onPatch, onDelete, onAdd, onAddVariant }) {
  // Null means "the order they were added", which is the sheet's own order and
  // the one people expect back when they stop sorting.
  const [sort, setSort] = useState(null)
  const [adding, setAdding] = useState('')

  const rows = sort
    ? [...items]
        .sort((a, b) => {
          const left = sortValue(a, sort.key)
          const right = sortValue(b, sort.key)
          if (left === right) return a.position - b.position
          return (left > right ? 1 : -1) * (sort.direction === 'asc' ? 1 : -1)
        })
        .map((item) => ({ item, showCategory: true, showName: true }))
    : groupRuns(items)

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
      <table className="w-full min-w-[1080px] border-collapse text-sm whitespace-nowrap">
        <thead>
          <tr className="border-y border-border bg-surface-2">
            {COLUMNS.map((column) => (
              <th
                key={column.key}
                scope="col"
                colSpan={column.span}
                className={`${column.width ?? ''} border-r border-border px-2 py-2 text-left text-xs font-semibold tracking-wide text-text-muted`}
              >
                <SortHeader column={column} sort={sort} onSort={toggleSort} />
              </th>
            ))}
            <th scope="col" className="w-10">
              <span className="sr-only">選單</span>
            </th>
          </tr>
        </thead>

        <tbody>
          {rows.map(({ item, showCategory, showName }) => (
            <GridRow
              key={item.id}
              item={item}
              showCategory={showCategory}
              showName={showName}
              continuesRun={!showName}
              categories={categories}
              locations={locations}
              onPatch={onPatch}
              onDelete={onDelete}
              onAddVariant={onAddVariant}
            />
          ))}

          <tr className="border-t border-border">
            <td colSpan={CELL_COUNT} className="border-b border-border">
              <form onSubmit={submitNew}>
                <input
                  value={adding}
                  onChange={(event) => setAdding(event.target.value)}
                  placeholder="▸ 新增一列…"
                  aria-label="新增一列"
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
