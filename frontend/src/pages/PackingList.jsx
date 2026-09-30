/**
 * One packing list, in one of two views.
 *
 * **表格** (the sheet) is where a list is planned: every column visible, every
 * cell editable where it sits. **清單** (the checklist) is where it is worked
 * through on a phone: a tick and a name.
 *
 * The switch names two whole views rather than an axis to group by. The screen
 * this replaced offered "When / Category / Bag", which is a question about the
 * data model, asked of someone who wants to pack a bag.
 */

import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { endpoints } from '../api/endpoints'
import { Checklist } from '../components/Checklist'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { Grid } from '../components/Grid'
import { ErrorState, LoadingState } from '../components/States'
import { send, useApiMutation, useApiQuery } from '../hooks/useApiQuery'
import { leavingText, progressParts } from '../lib/listHeader'

const VIEW_STORAGE_KEY = 'travel.packing.view'

const RESET_BODY =
  '所有已打包的項目會改回未打包，已打包數量歸零，Double Check 改回未確認。不需打包的項目不變。'

function initialView() {
  // Remembered per viewer; a phone-width first visit starts on the checklist,
  // because a sheet on a 375px screen is a horizontal scroll bar.
  try {
    const stored = localStorage.getItem(VIEW_STORAGE_KEY)
    if (stored === 'sheet' || stored === 'checklist') return stored
  } catch {
    // Private windows and blocked site data both throw here.
  }
  return typeof window !== 'undefined' && window.innerWidth < 720
    ? 'checklist'
    : 'sheet'
}

function Progress({ items }) {
  const parts = progressParts(items)
  if (!parts) return null
  return (
    <p className="m-0 text-sm text-text-muted">
      {parts.settled}
      {parts.unchecked && <span className="text-warning">{parts.unchecked}</span>}
      {parts.ready && <span className="text-success">{parts.ready}</span>}
    </p>
  )
}

/**
 * When the list leaves. A list's own date is edited here; a date that comes
 * from a This time leg is only shown — it is changed on the leg.
 */
function Departure({ list, onChange }) {
  const [editing, setEditing] = useState(false)
  const text = leavingText(list.departure_at, list.departure_source, new Date())

  if (list.departure_source === 'trip_leg') {
    return <p className="m-0 mt-1 text-sm text-text-faint">{text}</p>
  }
  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => setEditing(true)}
        title="點一下修改出發日期"
        className="mt-1 block text-left text-sm text-text-faint"
        style={{ minHeight: 0 }}
      >
        {text}
      </button>
    )
  }
  return (
    <input
      type="date"
      autoFocus
      defaultValue={list.departure_at ?? ''}
      aria-label="出發日期"
      onBlur={(event) => {
        setEditing(false)
        const next = event.target.value || null
        if (next !== list.departure_at) onChange(next)
      }}
      onKeyDown={(event) => {
        if (event.key === 'Enter') event.target.blur()
        if (event.key === 'Escape') setEditing(false)
      }}
      className="mt-1 block rounded-md border border-border bg-canvas px-2 py-1 text-sm text-text"
    />
  )
}

export default function PackingList() {
  const { listId } = useParams()
  const key = useMemo(() => ['packing-list', listId], [listId])
  const list = useApiQuery(key, endpoints.packingLists.detail(listId))
  const options = useApiQuery(['label-options'], endpoints.labelOptions.index())

  const [view, setView] = useState(initialView)
  const [confirmingReset, setConfirmingReset] = useState(false)

  const invalidate = [key, ['packing-lists'], ['label-options']]

  const patch = useApiMutation({
    invalidate,
    mutationFn: ({ id, changes }) =>
      send(endpoints.packingItems.detail(id), 'PATCH', changes),
  })
  const add = useApiMutation({
    invalidate,
    mutationFn: (payload) => send(endpoints.packingLists.items(listId), 'POST', payload),
  })
  const remove = useApiMutation({
    invalidate,
    mutationFn: (id) => send(endpoints.packingItems.detail(id), 'DELETE'),
  })
  const reset = useApiMutation({
    invalidate: [key, ['packing-lists']],
    mutationFn: () => send(endpoints.packingLists.reset(listId), 'POST'),
  })
  const patchList = useApiMutation({
    invalidate: [key, ['packing-lists']],
    mutationFn: (changes) => send(endpoints.packingLists.detail(listId), 'PATCH', changes),
  })

  const chooseView = (next) => {
    setView(next)
    try {
      localStorage.setItem(VIEW_STORAGE_KEY, next)
    } catch {
      // Not worth failing a render over.
    }
  }

  if (list.isLoading) return <LoadingState label="載入清單中…" />
  if (list.isError) return <ErrorState error={list.error} onRetry={list.refetch} />

  const items = list.data.items
  const values = (kind) =>
    (options.data || []).filter((row) => row.kind === kind).map((row) => row.value)

  const handlers = {
    onPatch: (id, changes) => patch.mutate({ id, changes }),
    onDelete: (id) => remove.mutate(id),
    onAdd: (name) => add.mutate({ name }),
    // A variant lands directly under the row it came from, carrying its
    // category and name — the sheet then blanks both, so it reads as one item.
    onAddVariant: (item) =>
      add.mutate({ name: item.name, category: item.category, after_id: item.id }),
  }

  return (
    <main className="mx-auto max-w-6xl pb-16">
      <div className="px-4 pt-6">
        <Link to="/" className="text-sm text-text-faint no-underline">
          ← 所有清單
        </Link>
        <div className="mt-2 flex flex-wrap items-baseline justify-between gap-2">
          <h1 className="m-0 text-xl font-semibold">{list.data.name}</h1>
          <div className="flex gap-1 rounded-md border border-border p-0.5">
            {[
              ['sheet', '表格'],
              ['checklist', '清單'],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => chooseView(value)}
                aria-pressed={view === value}
                className={`rounded-sm px-3 text-sm ${
                  view === value ? 'bg-brand text-on-brand' : 'text-text-muted'
                }`}
                style={{ minHeight: 36 }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <Departure
          list={list.data}
          onChange={(departure_at) => patchList.mutate({ departure_at })}
        />
        <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
          <Progress items={items} />
          {items.length > 0 && (
            <button
              type="button"
              onClick={() => setConfirmingReset(true)}
              className="rounded-md border border-border-strong px-3 text-sm text-text-muted"
              style={{ minHeight: 36 }}
            >
              重設狀態
            </button>
          )}
        </div>
      </div>

      <div className="mt-4">
        {view === 'sheet' ? (
          <Grid
            items={items}
            categories={values('category')}
            locations={values('location')}
            {...handlers}
          />
        ) : (
          <Checklist items={items} {...handlers} />
        )}
      </div>

      {confirmingReset && (
        <ConfirmDialog
          title="重設狀態？"
          body={RESET_BODY}
          confirmLabel="重設"
          onConfirm={() => {
            setConfirmingReset(false)
            reset.mutate()
          }}
          onCancel={() => setConfirmingReset(false)}
        />
      )}
    </main>
  )
}
