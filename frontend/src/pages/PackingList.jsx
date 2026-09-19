/**
 * One packing list, in one of two views.
 *
 * **Sheet** is where a list is planned: every column visible, every cell
 * editable where it sits. **Checklist** is where it is worked through on a
 * phone: a tick and a name.
 *
 * The switch names two whole views rather than an axis to group by. The screen
 * this replaced offered "When / Category / Bag", which is a question about the
 * data model, asked of someone who wants to pack a bag.
 */

import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { endpoints } from '../api/endpoints'
import { Checklist } from '../components/Checklist'
import { Grid } from '../components/Grid'
import { ErrorState, LoadingState } from '../components/States'
import { send, useApiMutation, useApiQuery } from '../hooks/useApiQuery'
import { daysUntil } from '../lib/timing'

const VIEW_STORAGE_KEY = 'travel.packing.view'

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

function leaving(departureAt) {
  if (!departureAt) return 'No date set'
  const days = daysUntil(departureAt, new Date())
  if (days === 0) return `Leaving today · ${departureAt}`
  if (days === 1) return `Leaving tomorrow · ${departureAt}`
  if (days < 0) return `Left ${-days} days ago · ${departureAt}`
  return `Leaving in ${days} days · ${departureAt}`
}

function Progress({ items }) {
  if (items.length === 0) return null
  const settled = items.filter((item) => item.status !== 'not_packed').length
  const unchecked = items.filter(
    (item) => item.needs_double_check && !item.double_checked,
  ).length
  const ready = settled === items.length && unchecked === 0

  return (
    <p className="m-0 text-sm text-text-muted">
      {settled} of {items.length} settled
      {unchecked > 0 && <span className="text-warning"> · {unchecked} to check</span>}
      {ready && <span className="text-success"> · ready to go</span>}
    </p>
  )
}

export default function PackingList() {
  const { listId } = useParams()
  const key = useMemo(() => ['packing-list', listId], [listId])
  const list = useApiQuery(key, endpoints.packingLists.detail(listId))
  const options = useApiQuery(['label-options'], endpoints.labelOptions.index())

  const [view, setView] = useState(initialView)

  const invalidate = [key, ['packing-lists'], ['label-options']]

  const patch = useApiMutation({
    invalidate,
    mutationFn: ({ id, changes }) =>
      send(endpoints.packingItems.detail(id), 'PATCH', changes),
  })
  const add = useApiMutation({
    invalidate,
    mutationFn: (name) => send(endpoints.packingLists.items(listId), 'POST', { name }),
  })
  const remove = useApiMutation({
    invalidate,
    mutationFn: (id) => send(endpoints.packingItems.detail(id), 'DELETE'),
  })

  const chooseView = (next) => {
    setView(next)
    try {
      localStorage.setItem(VIEW_STORAGE_KEY, next)
    } catch {
      // Not worth failing a render over.
    }
  }

  if (list.isLoading) return <LoadingState label="Loading the list…" />
  if (list.isError) return <ErrorState error={list.error} onRetry={list.refetch} />

  const items = list.data.items
  const values = (kind) =>
    (options.data || []).filter((row) => row.kind === kind).map((row) => row.value)

  const onPatch = (id, changes) => patch.mutate({ id, changes })

  return (
    <main className="mx-auto max-w-5xl pb-16">
      <div className="px-4 pt-6">
        <Link to="/" className="text-sm text-text-faint no-underline">
          ← All lists
        </Link>
        <div className="mt-2 flex flex-wrap items-baseline justify-between gap-2">
          <h1 className="m-0 text-xl font-semibold">{list.data.name}</h1>
          <div className="flex gap-1 rounded-md border border-border p-0.5">
            {[
              ['sheet', 'Sheet'],
              ['checklist', 'Checklist'],
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
        <p className="m-0 mt-1 text-sm text-text-faint">{leaving(list.data.departure_at)}</p>
        <div className="mt-1">
          <Progress items={items} />
        </div>
      </div>

      <div className="mt-4">
        {view === 'sheet' ? (
          <Grid
            items={items}
            categories={values('category')}
            bags={values('bag')}
            onPatch={onPatch}
            onDelete={(id) => remove.mutate(id)}
            onAdd={(name) => add.mutate(name)}
          />
        ) : (
          <Checklist items={items} onPatch={onPatch} onAdd={(name) => add.mutate(name)} />
        )}
      </div>
    </main>
  )
}
