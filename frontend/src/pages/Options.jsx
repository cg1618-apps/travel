/**
 * The remembered category and bag values: rename, reorder, prune.
 *
 * Renaming says how many items it will rewrite before it does, because these
 * are suggestions rather than references and a rename is a bulk edit of real
 * data wearing a tidy-up's clothes.
 */

import { useState } from 'react'
import { Link } from 'react-router-dom'

import { endpoints } from '../api/endpoints'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { send, useApiMutation, useApiQuery } from '../hooks/useApiQuery'

const KEY = ['label-options']

function Option({ option, onRename, onDelete }) {
  const [value, setValue] = useState(option.value)
  const changed = value.trim() && value !== option.value

  return (
    <li className="flex items-center gap-2 border-b border-border px-4 py-2 last:border-b-0">
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        aria-label={`Rename ${option.value}`}
        className="min-w-0 flex-1 rounded-md border border-border bg-canvas px-3 py-2 text-base"
      />
      <span className="w-16 shrink-0 text-right text-xs text-text-faint">
        {option.usage_count} {option.usage_count === 1 ? 'item' : 'items'}
      </span>
      {changed ? (
        <button
          type="button"
          onClick={() => onRename(option, value.trim())}
          className="rounded-md bg-brand px-3 text-sm text-on-brand"
        >
          Rename
        </button>
      ) : (
        <button
          type="button"
          onClick={() => onDelete(option)}
          aria-label={`Remove ${option.value} from the suggestions`}
          className="px-3 text-text-faint"
        >
          ✕
        </button>
      )}
    </li>
  )
}

function Group({ title, options, onRename, onDelete }) {
  return (
    <section className="mt-6">
      <h2 className="mx-4 mb-2 text-xs font-semibold uppercase tracking-wide text-text-faint">
        {title}
      </h2>
      {options.length === 0 ? (
        <EmptyState>Nothing remembered yet. Type one on an item and it appears here.</EmptyState>
      ) : (
        <ul className="list-none border-y border-border bg-surface p-0">
          {options.map((option) => (
            <Option
              // Keyed by value as well as id so the input resets after a merge
              // replaces the row underneath it.
              key={`${option.id}-${option.value}`}
              option={option}
              onRename={onRename}
              onDelete={onDelete}
            />
          ))}
        </ul>
      )}
    </section>
  )
}

export default function Options() {
  const options = useApiQuery(KEY, endpoints.labelOptions.index())
  const [notice, setNotice] = useState(null)

  // Item queries are invalidated too: a rename rewrites the items themselves,
  // so a list left in the cache would still show the old spelling.
  const invalidate = [KEY, ['packing-list'], ['packing-lists']]

  const rename = useApiMutation({
    invalidate,
    mutationFn: ({ id, value }) =>
      send(endpoints.labelOptions.detail(id), 'PATCH', { value }),
  })

  const remove = useApiMutation({
    invalidate,
    mutationFn: (id) => send(endpoints.labelOptions.detail(id), 'DELETE'),
  })

  if (options.isLoading) return <LoadingState label="Loading options…" />
  if (options.isError) return <ErrorState error={options.error} onRetry={options.refetch} />

  const onRename = (option, value) => {
    const collision = options.data.find(
      (row) => row.kind === option.kind && row.value === value,
    )
    setNotice(
      collision
        ? `Merged into “${value}”. ${option.usage_count} item(s) rewritten.`
        : `Renamed. ${option.usage_count} item(s) rewritten.`,
    )
    rename.mutate({ id: option.id, value })
  }

  const byKind = (kind) => options.data.filter((row) => row.kind === kind)

  return (
    <main className="mx-auto max-w-2xl pb-16">
      <div className="px-4 pt-6">
        <Link to="/" className="text-sm text-text-faint no-underline">
          ← All lists
        </Link>
        <h1 className="mt-2 mb-1 text-xl font-semibold">Common options</h1>
        <p className="m-0 text-sm text-text-faint">
          Suggestions for category and bag, remembered from what you type. Removing one
          leaves your items alone.
        </p>
      </div>

      {notice && (
        <p className="mx-4 mt-4 rounded-md bg-brand-soft px-3 py-2 text-sm text-brand">
          {notice}
        </p>
      )}

      <Group title="Category" options={byKind('category')} onRename={onRename} onDelete={(option) => remove.mutate(option.id)} />
      <Group title="Bag" options={byKind('bag')} onRename={onRename} onDelete={(option) => remove.mutate(option.id)} />
    </main>
  )
}
