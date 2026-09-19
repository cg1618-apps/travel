/**
 * The three shelves, and creating a list.
 *
 * `evict_next` comes from the index rather than from the 409, because the
 * refusal's detail is a plain string and the dialog needs the list's id to
 * offer "save it instead". See docs/api.md.
 */

import { useState } from 'react'
import { Link } from 'react-router-dom'

import { endpoints } from '../api/endpoints'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { EvictDialog } from '../components/EvictDialog'
import { send, useApiMutation, useApiQuery } from '../hooks/useApiQuery'

const INDEX_KEY = ['packing-lists']

function Shelf({ title, note, lists, empty }) {
  return (
    <section className="mt-6">
      <h2 className="mx-4 mb-2 text-xs font-semibold uppercase tracking-wide text-text-faint">
        {title}
        {note && <span className="ml-2 font-normal normal-case">{note}</span>}
      </h2>
      {lists.length === 0 ? (
        <EmptyState>{empty}</EmptyState>
      ) : (
        <ul className="list-none border-y border-border bg-surface p-0">
          {lists.map((row) => (
            <li key={row.id} className="border-b border-border last:border-b-0">
              <Link
                to={`/lists/${row.id}`}
                className="flex items-center justify-between px-4 py-3 no-underline"
              >
                <span className="text-text">{row.name}</span>
                <span className="text-xs text-text-faint">
                  {row.departure_at || '—'}
                  {row.leg ? ` · ${row.leg}` : ''}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default function PackingLists() {
  const index = useApiQuery(INDEX_KEY, endpoints.packingLists.index())
  const [name, setName] = useState('')
  const [departureAt, setDepartureAt] = useState('')
  const [copyFromId, setCopyFromId] = useState('')
  const [refusal, setRefusal] = useState(null)

  const create = useApiMutation({
    invalidate: [INDEX_KEY],
    mutationFn: (payload) => send(endpoints.packingLists.index(), 'POST', payload),
    onSuccess: () => {
      setName('')
      setDepartureAt('')
      setCopyFromId('')
      setRefusal(null)
    },
    onError: (error) => {
      // 409 is a decision to put to the user, not a failure to report.
      if (error.status === 409) setRefusal(error.message)
    },
  })

  const saveList = useApiMutation({
    invalidate: [INDEX_KEY],
    mutationFn: (id) => send(endpoints.packingLists.detail(id), 'PATCH', { saved: true }),
  })

  if (index.isLoading) return <LoadingState label="Loading your lists…" />
  if (index.isError) return <ErrorState error={index.error} onRetry={index.refetch} />

  const { recent, saved, templates, evict_next: evictNext } = index.data
  const copyable = [...templates, ...saved, ...recent]

  const payload = () => ({
    name: name.trim(),
    departure_at: departureAt || null,
    copy_from_id: copyFromId ? Number(copyFromId) : null,
  })

  const submit = (event) => {
    event.preventDefault()
    if (!name.trim()) return
    create.mutate(payload())
  }

  return (
    <main className="mx-auto max-w-2xl pb-16">
      <h1 className="px-4 pt-6 text-xl font-semibold">Packing</h1>

      <form onSubmit={submit} className="mt-4 border-y border-border bg-surface px-4 py-4">
        <label className="block text-xs font-semibold uppercase tracking-wide text-text-faint">
          New list
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Where to?"
            className="mt-1 block w-full rounded-md border border-border bg-canvas px-3 py-2 text-base font-normal normal-case text-text"
          />
        </label>

        <div className="mt-3 flex flex-wrap gap-3">
          <label className="flex-1 text-xs text-text-faint">
            Leaving
            <input
              type="date"
              value={departureAt}
              onChange={(event) => setDepartureAt(event.target.value)}
              className="mt-1 block w-full rounded-md border border-border bg-canvas px-3 py-2 text-base text-text"
            />
          </label>
          <label className="flex-1 text-xs text-text-faint">
            Start from
            <select
              value={copyFromId}
              onChange={(event) => setCopyFromId(event.target.value)}
              className="mt-1 block w-full rounded-md border border-border bg-canvas px-3 py-2 text-base text-text"
            >
              <option value="">Nothing</option>
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
          disabled={!name.trim() || create.isPending}
          className="mt-4 w-full rounded-md bg-brand px-4 font-medium text-on-brand disabled:opacity-40"
        >
          Create list
        </button>

        {create.isError && create.error.status !== 409 && (
          <p className="mt-2 text-sm text-danger">{create.error.message}</p>
        )}
      </form>

      <Shelf
        title="Recent"
        note={`${recent.length} of 3`}
        lists={recent}
        empty="No lists on the go."
      />
      <Shelf title="Saved" lists={saved} empty="Nothing saved yet." />
      <Shelf
        title="Templates"
        lists={templates}
        empty="No templates. Mark a list as a template to start from it next time."
      />

      {refusal && (
        <EvictDialog
          message={refusal}
          evicting={evictNext}
          onSaveInstead={async () => {
            // Save every list in the slot first, then retry unconfirmed - so
            // the retry succeeds because there is room, not because it was
            // forced through.
            await Promise.all(evictNext.map((row) => saveList.mutateAsync(row.id)))
            create.mutate(payload())
          }}
          onConfirm={() => create.mutate({ ...payload(), evict_confirmed: true })}
          onCancel={() => setRefusal(null)}
        />
      )}
    </main>
  )
}
