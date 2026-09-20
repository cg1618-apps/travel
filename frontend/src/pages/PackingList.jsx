/**
 * One list, grouped by when each thing is due.
 *
 * Timing is the default grouping rather than a filter over a category list,
 * because the question actually being asked the evening before a flight is
 * "what do I do tonight" - and a category-grouped screen cannot answer it.
 */

import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { endpoints } from '../api/endpoints'
import { ItemEditor } from '../components/ItemEditor'
import { ItemRow } from '../components/ItemRow'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { send, useApiMutation, useApiQuery } from '../hooks/useApiQuery'
import { TIMINGS, TIMING_LABELS, dueTimings } from '../lib/timing'

const GROUPINGS = [
  { key: 'timing', label: 'When' },
  { key: 'category', label: 'Category' },
  { key: 'bag', label: 'Bag' },
]

const GROUPING_STORAGE_KEY = 'travel.packing.grouping'

function readStoredGrouping() {
  // A per-viewer convenience, so browser storage is the right home for it -
  // and it has to survive the accessor throwing in a private window.
  try {
    const stored = localStorage.getItem(GROUPING_STORAGE_KEY)
    return GROUPINGS.some((option) => option.key === stored) ? stored : 'timing'
  } catch {
    return 'timing'
  }
}

function groupItems(items, grouping) {
  if (grouping === 'timing') {
    return TIMINGS.map((key) => ({
      key,
      label: TIMING_LABELS[key],
      items: items.filter((item) => item.timing === key),
    }))
  }
  const values = [...new Set(items.map((item) => item[grouping] || ''))].sort()
  return values.map((value) => ({
    key: value || '(none)',
    label: value || 'Uncategorised',
    items: items.filter((item) => (item[grouping] || '') === value),
  }))
}

function Progress({ items }) {
  const resolved = items.filter((item) => item.status !== 'not_packed').length
  const outstanding = items.filter(
    (item) => item.needs_double_check && !item.double_checked,
  ).length
  const finished = resolved === items.length && outstanding === 0 && items.length > 0

  return (
    <p className="m-0 text-sm text-text-muted">
      {resolved} of {items.length} settled
      {outstanding > 0 && (
        <span className="text-warning"> · {outstanding} to double check</span>
      )}
      {finished && <span className="text-success"> · ready</span>}
    </p>
  )
}

export default function PackingList() {
  const { listId } = useParams()
  const key = useMemo(() => ['packing-list', listId], [listId])
  const list = useApiQuery(key, endpoints.packingLists.detail(listId))

  const [grouping, setGrouping] = useState(readStoredGrouping)
  const [newItem, setNewItem] = useState('')
  const [editing, setEditing] = useState(null)

  const options = useApiQuery(['label-options'], endpoints.labelOptions.index())

  const invalidate = [key, ['packing-lists']]

  const addItem = useApiMutation({
    invalidate,
    mutationFn: (name) =>
      send(endpoints.packingLists.items(listId), 'POST', { name }),
    onSuccess: () => setNewItem(''),
  })

  const patchItem = useApiMutation({
    // Also the options: a category typed into the editor becomes a suggestion,
    // and the datalist would otherwise not show it until a reload.
    invalidate: [...invalidate, ['label-options']],
    mutationFn: ({ id, changes }) =>
      send(endpoints.packingItems.detail(id), 'PATCH', changes),
  })

  const removeItem = useApiMutation({
    invalidate,
    mutationFn: (id) => send(endpoints.packingItems.detail(id), 'DELETE'),
    onSuccess: () => setEditing(null),
  })

  const chooseGrouping = (value) => {
    setGrouping(value)
    try {
      localStorage.setItem(GROUPING_STORAGE_KEY, value)
    } catch {
      // A remembered tab is not worth failing a render over.
    }
  }

  if (list.isLoading) return <LoadingState label="Loading the list…" />
  if (list.isError) return <ErrorState error={list.error} onRetry={list.refetch} />

  const items = list.data.items
  const due = dueTimings(list.data.departure_at, new Date())
  const groups = groupItems(items, grouping)

  return (
    <main className="mx-auto max-w-2xl pb-16">
      <div className="px-4 pt-6">
        <Link to="/" className="text-sm text-text-faint no-underline">
          ← All lists
        </Link>
        <h1 className="mt-2 mb-1 text-xl font-semibold">{list.data.name}</h1>
        <p className="m-0 text-sm text-text-faint">
          {list.data.departure_at ? `Leaving ${list.data.departure_at}` : 'No date set'}
        </p>
        <div className="mt-2">
          <Progress items={items} />
        </div>
      </div>

      <div className="mt-4 flex gap-1 px-4" role="tablist" aria-label="Group items by">
        {GROUPINGS.map((option) => (
          <button
            key={option.key}
            type="button"
            role="tab"
            aria-selected={grouping === option.key}
            onClick={() => chooseGrouping(option.key)}
            className={`rounded-md px-3 text-sm ${
              grouping === option.key
                ? 'bg-brand-soft text-brand'
                : 'text-text-muted'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault()
          if (newItem.trim()) addItem.mutate(newItem.trim())
        }}
        className="mt-4 flex gap-2 px-4"
      >
        <input
          value={newItem}
          onChange={(event) => setNewItem(event.target.value)}
          placeholder="Add something"
          aria-label="Add an item"
          className="min-w-0 flex-1 rounded-md border border-border bg-surface px-3 py-2 text-base"
        />
        <button
          type="submit"
          disabled={!newItem.trim()}
          className="rounded-md bg-brand px-4 font-medium text-on-brand disabled:opacity-40"
        >
          Add
        </button>
      </form>

      {items.length === 0 ? (
        <EmptyState>Nothing on this list yet.</EmptyState>
      ) : (
        groups.map((group) => {
          if (group.items.length === 0) return null
          // Only the timing grouping has a notion of "due"; the others are
          // just ways of looking at the same items.
          const isDue = grouping === 'timing' && due.has(group.key)

          return (
            <section key={group.key} className="mt-6">
              <h2
                className={`mx-4 mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide ${
                  isDue ? 'text-brand' : 'text-text-faint'
                }`}
              >
                {group.label}
                {isDue && (
                  <span className="rounded-sm bg-brand-soft px-1.5 py-0.5 normal-case">
                    due now
                  </span>
                )}
              </h2>
              <ul
                className={`list-none border-y bg-surface p-0 ${
                  isDue ? 'border-brand/40' : 'border-border'
                }`}
              >
                {group.items.map((item) => (
                  <ItemRow
                    key={item.id}
                    item={item}
                    onCycleStatus={(target, status) =>
                      patchItem.mutate({ id: target.id, changes: { status } })
                    }
                    onToggleDoubleCheck={(target) =>
                      patchItem.mutate({
                        id: target.id,
                        changes: { double_checked: !target.double_checked },
                      })
                    }
                    onEdit={setEditing}
                  />
                ))}
              </ul>
            </section>
          )
        })
      )}

      {editing && (
        <ItemEditor
          item={editing}
          categories={(options.data || []).filter((row) => row.kind === 'category')}
          bags={(options.data || []).filter((row) => row.kind === 'bag')}
          onSave={(changes) => {
            patchItem.mutate({ id: editing.id, changes })
            setEditing(null)
          }}
          onDelete={(target) => removeItem.mutate(target.id)}
          onClose={() => setEditing(null)}
        />
      )}
    </main>
  )
}
