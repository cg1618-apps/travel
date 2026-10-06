/**
 * The packing list as a sheet: one row per thing, one column per fact.
 *
 * This is the view the app is planned in, and it reads like the owner's Google
 * Sheet — the same columns in the same order, in the sheet's own words. Every
 * cell edits where it sits. A single row lives in `GridRow.jsx`.
 *
 * Rows are grouped by 類別, and a group is always together: each one is its
 * own `<tbody>`, drawn with a border round it. Rows are dragged within their
 * group by the grip beside their number; the groups themselves are ordered in
 * 排序類別 (`GroupOrderDialog`), so a drag never has to mean two things. Both
 * write the list's whole order in one request.
 *
 * Inside a group a category or a name is written once per run and left blank
 * beneath, as in the sheet, so an item and its variants read as one block.
 *
 * 打包狀態, Double Check, 打包時機, 需求 and 取得地點 filter from their
 * headers, and the header row stays on screen while the sheet scrolls. The
 * toolbar's 未打包 / 全部 switch and 打包時機 chips are shortcuts onto the same
 * filters, not filters of their own. A filtered sheet cannot be reordered: a
 * drop between two visible rows says nothing about where the hidden ones go.
 *
 * Every row carries its number in the whole list, in the column pinned to the
 * left edge, so a filter leaves gaps rather than renumbering.
 *
 * New rows are added several at a time and saved together (`NewRows`), so
 * each lands in its group complete.
 */

import { useCallback, useState } from 'react'

import { applyFilters, isFiltering, statusScope, toggleValue, withStatusScope } from '../lib/filters'
import { groupByCategory, groupRuns, moveInGroup, orderIds, rowNumbers } from '../lib/grouping'
import { itemTitle } from '../lib/rowMenu'
import { TIMING_LABELS } from '../lib/labels'
import { TIMINGS } from '../lib/timing'
import { CHECK_TONES, NEED_TONES, STATUS_TONES, TIMING_TONES, toneClass, toneForText } from '../lib/tones'
import { FilterMenu } from './FilterMenu'
import { GroupOrderDialog, UNCATEGORISED } from './GroupOrderDialog'
import { GridRow } from './GridRow'
import { NewRows } from './NewRows'
import { SortableList } from './Sortable'

// `bag` is not a column: the sheet has none. It stays in the data.
const COLUMNS = [
  { key: 'category', label: '類別', width: 'w-28' },
  { key: 'name', label: '項目', span: 2 },
  { key: 'quantity', label: '數量', width: 'w-24' },
  { key: 'quantity_packed', label: '已打包數量', width: 'w-24' },
  { key: 'status', label: '打包狀態', width: 'w-28', filter: true },
  { key: 'check', label: 'Double Check', width: 'w-28', filter: true },
  { key: 'timing', label: '打包時機', width: 'w-28', filter: true },
  { key: 'need', label: '需求', width: 'w-20', filter: true },
  { key: 'location', label: '取得地點', width: 'w-28', filter: true },
  { key: 'notes', label: '備註', width: 'w-44' },
]
// The number and grip columns, the columns, and the ⋯ column.
const CELL_COUNT = COLUMNS.reduce((sum, column) => sum + (column.span ?? 1), 0) + 3

/** The tone each filterable column's values carry, for the filter list. */
const FILTER_TONES = {
  status: (value) => STATUS_TONES[value],
  check: (value) => CHECK_TONES[value],
  timing: (value) => TIMING_TONES[value],
  need: (value) => NEED_TONES[value],
  location: toneForText,
}

// A sticky header needs its scroll container to be the one that scrolls. A
// wide screen fits the sheet, so the page scrolls and nothing here clips; a
// narrow one scrolls sideways inside this box, which is then also given the
// vertical scroll so the header can stick to its top.
const SCROLLER =
  'max-h-[calc(100dvh-1rem)] overflow-auto min-[1160px]:max-h-none min-[1160px]:overflow-visible'

// The header's own borders scroll away under border-collapse, so the line
// under it is a shadow.
const HEAD_BASE =
  'border-r border-border bg-surface-2 px-2 py-2 text-left text-xs font-semibold tracking-wide text-text-muted'
const HEAD_CELL = `${HEAD_BASE} shadow-[inset_0_-1px_0_var(--c-border)]`
// The pinned # header: both edges as shadows, since neither border stays.
const NUMBER_HEAD = `${HEAD_BASE} sticky left-0 z-[1] min-w-10 px-1 text-center shadow-[inset_-1px_0_0_var(--c-border),inset_0_-1px_0_var(--c-border)]`

const smallButton = 'rounded-md border border-border-strong px-3 text-sm text-text-muted'

const STATUS_SCOPES = [
  ['not_packed', '未打包'],
  ['all', '全部'],
]

/** 未打包 / 全部: the 打包狀態 filter, one tap away. */
function StatusScope({ filters, onChange }) {
  const scope = statusScope(filters)
  return (
    <div role="group" aria-label="顯示" className="flex gap-1 rounded-md border border-border p-0.5">
      {STATUS_SCOPES.map(([value, label]) => (
        <button
          key={value}
          type="button"
          onClick={() => onChange(withStatusScope(filters, value))}
          aria-pressed={scope === value}
          className={`rounded-sm px-3 text-sm ${
            scope === value ? 'bg-brand text-on-brand' : 'text-text-muted'
          }`}
          style={{ minHeight: 30 }}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

/** 打包時機 as chips: the same filter as its header, ticked in the open. */
function TimingChips({ selected, onToggle }) {
  return (
    <div role="group" aria-label="打包時機" className="flex flex-wrap items-center gap-1">
      <span className="text-sm text-text-faint">打包時機</span>
      {TIMINGS.map((timing) => {
        const on = selected.includes(timing)
        return (
          <button
            key={timing}
            type="button"
            onClick={() => onToggle(timing)}
            aria-pressed={on}
            className={`rounded-sm border px-2 text-sm ${
              on ? `border-brand ${toneClass(TIMING_TONES[timing])}` : 'border-border text-text-muted'
            }`}
            style={{ minHeight: 30 }}
          >
            {TIMING_LABELS[timing]}
          </button>
        )
      })}
    </div>
  )
}

function Group({ group, numbers, sortable, onMove, rowProps }) {
  const ids = group.items.map((item) => item.id)
  const move = useCallback((from, to) => onMove(group.key, from, to), [group.key, onMove])

  return (
    <SortableList ids={ids} onMove={move} disabled={!sortable}>
      <tbody
        className="border-2 border-border-strong"
        aria-label={group.category ?? UNCATEGORISED}
      >
        {groupRuns(group.items).map(({ item, showCategory, showName }) => (
          <GridRow
            key={item.id}
            item={item}
            number={numbers.get(item.id)}
            showCategory={showCategory}
            showName={showName}
            continuesRun={!showName}
            sortLabel={itemTitle(item)}
            {...rowProps}
          />
        ))}
      </tbody>
    </SortableList>
  )
}

export function Grid({
  items,
  categories,
  locations,
  adding,
  onPatch,
  onDelete,
  onAddMany,
  onAddVariant,
  onReorder,
}) {
  const [filters, setFilters] = useState({})
  const [orderingGroups, setOrderingGroups] = useState(false)

  const filtering = isFiltering(filters)
  const shown = applyFilters(items, filters)
  const groups = groupByCategory(shown)
  const allGroups = groupByCategory(items)
  const numbers = rowNumbers(items)
  const toggleFilter = (key, value) => setFilters((current) => toggleValue(current, key, value))

  const onMove = useCallback(
    (groupKey, from, to) => onReorder(orderIds(moveInGroup(groupByCategory(items), groupKey, from, to))),
    [items, onReorder],
  )

  const rowProps = { categories, locations, onPatch, onDelete, onAddVariant }

  return (
    <>
      <div className="mb-2 flex flex-wrap items-center gap-2 px-4">
        <button
          type="button"
          onClick={() => setOrderingGroups(true)}
          disabled={allGroups.length < 2}
          className={`${smallButton} disabled:opacity-40`}
          style={{ minHeight: 36 }}
        >
          排序類別
        </button>
        <StatusScope filters={filters} onChange={setFilters} />
        <TimingChips
          selected={filters.timing ?? []}
          onToggle={(timing) => toggleFilter('timing', timing)}
        />
        {filtering && (
          <>
            <span className="text-sm text-text-muted">
              篩選中：顯示 {shown.length} / {items.length} 項，不能拖曳排序
            </span>
            <button
              type="button"
              onClick={() => setFilters({})}
              className={smallButton}
              style={{ minHeight: 36 }}
            >
              清除所有篩選
            </button>
          </>
        )}
      </div>

      <div className={SCROLLER}>
        <table className="w-full min-w-[1110px] border-collapse text-sm whitespace-nowrap">
          <thead className="sticky top-0 z-10">
            <tr>
              <th scope="col" className={NUMBER_HEAD}>
                #
              </th>
              <th scope="col" className={`${HEAD_CELL} w-8 px-0`}>
                <span className="sr-only">排序</span>
              </th>
              {COLUMNS.map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  colSpan={column.span}
                  className={`${column.width ?? ''} ${HEAD_CELL}`}
                >
                  {column.filter ? (
                    <FilterMenu
                      column={column.key}
                      label={column.label}
                      items={items}
                      selected={filters[column.key] ?? []}
                      toneFor={FILTER_TONES[column.key]}
                      onToggle={(value) => toggleFilter(column.key, value)}
                      onClear={() => setFilters((current) => ({ ...current, [column.key]: [] }))}
                    />
                  ) : (
                    column.label
                  )}
                </th>
              ))}
              <th scope="col" className={`${HEAD_CELL} w-10`}>
                <span className="sr-only">選單</span>
              </th>
            </tr>
          </thead>

          {groups.map((group) => (
            <Group
              key={group.key}
              group={group}
              numbers={numbers}
              sortable={!filtering}
              onMove={onMove}
              rowProps={rowProps}
            />
          ))}

          {filtering && shown.length === 0 && (
            <tbody>
              <tr>
                <td colSpan={CELL_COUNT} className="px-4 py-6 text-center text-sm text-text-muted">
                  沒有符合篩選的項目。
                </td>
              </tr>
            </tbody>
          )}

          <NewRows
            cellCount={CELL_COUNT}
            firstNumber={items.length + 1}
            categories={categories}
            locations={locations}
            saving={adding}
            onSave={onAddMany}
          />
        </table>
      </div>

      {orderingGroups && (
        <GroupOrderDialog
          groups={allGroups}
          onSave={(order) => {
            setOrderingGroups(false)
            onReorder(orderIds(order))
          }}
          onCancel={() => setOrderingGroups(false)}
        />
      )}
    </>
  )
}

