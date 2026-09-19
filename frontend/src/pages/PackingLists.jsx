/**
 * Every list, as a sheet of lists.
 *
 * Three sections rather than three tabs, because there are rarely more than a
 * handful and scrolling past two short tables beats deciding which tab to look
 * in. Creating one is behind a button: the form used to sit open at the top of
 * the page, which made the first thing you saw a form rather than your lists.
 */

import { useState } from 'react'
import { Link } from 'react-router-dom'

import { endpoints } from '../api/endpoints'
import { EvictDialog } from '../components/EvictDialog'
import { ErrorState, LoadingState } from '../components/States'
import { send, useApiMutation, useApiQuery } from '../hooks/useApiQuery'
import { daysUntil } from '../lib/timing'

const INDEX_KEY = ['packing-lists']

function when(departureAt) {
  if (!departureAt) return '—'
  const days = daysUntil(departureAt, new Date())
  if (days === 0) return 'today'
  if (days === 1) return 'tomorrow'
  if (days < 0) return departureAt
  return `in ${days} days`
}

function Table({ title, count, rows, empty, onFlag }) {
  return (
    <section className="mt-8">
      <h2 className="mx-4 mb-2 text-xs font-semibold uppercase tracking-wide text-text-faint">
        {title}
        {count && <span className="ml-2 font-normal normal-case">{count}</span>}
      </h2>

      {rows.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-text-muted">{empty}</p>
      ) : (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-y border-border bg-surface-2 text-xs uppercase tracking-wide text-text-muted">
              <th scope="col" className="px-4 py-2 text-left font-semibold">
                List
              </th>
              <th scope="col" className="w-28 px-2 py-2 text-left font-semibold">
                Leaving
              </th>
              <th scope="col" className="w-28 px-2 py-2 text-left font-semibold">
                Packed
              </th>
              <th scope="col" className="w-16 px-2 py-2 text-center font-semibold">
                Keep
              </th>
              <th scope="col" className="w-20 px-2 py-2 text-center font-semibold">
                Template
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-b border-border bg-surface">
                <td className="px-4 py-2">
                  <Link to={`/lists/${row.id}`} className="text-text no-underline">
                    {row.name}
                  </Link>
                  {row.leg && (
                    <span className="ml-2 text-xs text-text-faint">{row.leg}</span>
                  )}
                </td>
                <td className="px-2 py-2 text-text-muted">{when(row.departure_at)}</td>
                <td className="px-2 py-2 tabular-nums text-text-muted">
                  {row.settled_count} / {row.item_count}
                </td>
                <td className="px-2 py-2 text-center">
                  <input
                    type="checkbox"
                    checked={row.saved}
                    onChange={(event) => onFlag(row, { saved: event.target.checked })}
                    aria-label={`Keep ${row.name} beyond the three-list limit`}
                    title="Keep this list beyond the three-list limit"
                    className="size-4 align-middle"
                  />
                </td>
                <td className="px-2 py-2 text-center">
                  <input
                    type="checkbox"
                    checked={row.template}
                    onChange={(event) => onFlag(row, { template: event.target.checked })}
                    aria-label={`Use ${row.name} as a template for new lists`}
                    title="Offer this list as a starting point for new ones"
                    className="size-4 align-middle"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

export default function PackingLists() {
  const index = useApiQuery(INDEX_KEY, endpoints.packingLists.index())
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState({ name: '', departure_at: '', copy_from_id: '' })
  const [refusal, setRefusal] = useState(null)

  const create = useApiMutation({
    invalidate: [INDEX_KEY],
    mutationFn: (payload) => send(endpoints.packingLists.index(), 'POST', payload),
    onSuccess: () => {
      setDraft({ name: '', departure_at: '', copy_from_id: '' })
      setOpen(false)
      setRefusal(null)
    },
    onError: (error) => {
      // A 409 is a decision to put to the person, not a failure to report.
      if (error.status === 409) setRefusal(error.message)
    },
  })

  const flag = useApiMutation({
    invalidate: [INDEX_KEY],
    mutationFn: ({ id, changes }) =>
      send(endpoints.packingLists.detail(id), 'PATCH', changes),
    onError: (error) => {
      if (error.status === 409) setRefusal(error.message)
    },
  })

  if (index.isLoading) return <LoadingState label="Loading your lists…" />
  if (index.isError) return <ErrorState error={index.error} onRetry={index.refetch} />

  const { recent, saved, templates, evict_next: evictNext } = index.data

  const copyable = [...templates, ...saved, ...recent]
  const payload = () => ({
    name: draft.name.trim(),
    departure_at: draft.departure_at || null,
    copy_from_id: draft.copy_from_id ? Number(draft.copy_from_id) : null,
  })

  const onFlag = (row, changes) => flag.mutate({ id: row.id, changes })

  return (
    <main className="mx-auto max-w-4xl pb-16">
      <div className="flex items-center justify-between px-4 pt-6">
        <h1 className="m-0 text-xl font-semibold">Packing lists</h1>
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="rounded-md bg-brand px-4 text-sm font-medium text-on-brand"
        >
          {open ? 'Cancel' : '+ New list'}
        </button>
      </div>

      {open && (
        <form
          onSubmit={(event) => {
            event.preventDefault()
            if (draft.name.trim()) create.mutate(payload())
          }}
          className="mx-4 mt-4 rounded-md border border-border bg-surface p-4"
        >
          <div className="flex flex-wrap gap-3">
            <label className="min-w-40 flex-1 text-xs text-text-faint">
              Name
              <input
                autoFocus
                value={draft.name}
                onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                placeholder="Sapporo"
                className="mt-1 block w-full rounded-md border border-border bg-canvas px-3 py-2 text-base text-text"
              />
            </label>
            <label className="text-xs text-text-faint">
              Leaving
              <input
                type="date"
                value={draft.departure_at}
                onChange={(event) =>
                  setDraft({ ...draft, departure_at: event.target.value })
                }
                className="mt-1 block rounded-md border border-border bg-canvas px-3 py-2 text-base text-text"
              />
            </label>
            <label className="text-xs text-text-faint">
              Copy items from
              <select
                value={draft.copy_from_id}
                onChange={(event) =>
                  setDraft({ ...draft, copy_from_id: event.target.value })
                }
                className="mt-1 block rounded-md border border-border bg-canvas px-3 py-2 text-base text-text"
              >
                <option value="">Start empty</option>
                {copyable.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.name}
                    {row.template ? ' (template)' : ''}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <button
            type="submit"
            disabled={!draft.name.trim() || create.isPending}
            className="mt-4 rounded-md bg-brand px-4 text-sm font-medium text-on-brand disabled:opacity-40"
          >
            Create
          </button>
          {create.isError && create.error.status !== 409 && (
            <p className="mt-2 text-sm text-danger">{create.error.message}</p>
          )}
        </form>
      )}

      <Table
        title="In progress"
        count={`${recent.length} of 3`}
        rows={recent}
        empty="No lists on the go. Make one above."
        onFlag={onFlag}
      />
      <Table
        title="Kept"
        rows={saved}
        empty="Tick “keep” on a list to stop it being replaced."
        onFlag={onFlag}
      />
      <Table
        title="Templates"
        rows={templates}
        empty="Tick “template” on a list to start future lists from it."
        onFlag={onFlag}
      />

      {refusal && (
        <EvictDialog
          message={refusal}
          evicting={evictNext}
          onSaveInstead={async () => {
            await Promise.all(
              evictNext.map((row) =>
                flag.mutateAsync({ id: row.id, changes: { saved: true } }),
              ),
            )
            create.mutate(payload())
          }}
          onConfirm={() => create.mutate({ ...payload(), evict_confirmed: true })}
          onCancel={() => setRefusal(null)}
        />
      )}
    </main>
  )
}
