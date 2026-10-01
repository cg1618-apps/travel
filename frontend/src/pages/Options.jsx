/**
 * The remembered values for every label kind — category, bag, location and
 * ticket type: rename, prune.
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
import { LABEL_KIND_LABELS } from '../lib/labels'

const KEY = ['label-options']

function Option({ option, onRename, onDelete }) {
  const [value, setValue] = useState(option.value)
  const changed = value.trim() && value !== option.value

  return (
    <li className="flex items-center gap-2 border-b border-border px-4 py-2 last:border-b-0">
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        aria-label={`重新命名「${option.value}」`}
        className="min-w-0 flex-1 rounded-md border border-border bg-canvas px-3 py-2 text-base"
      />
      <span className="w-20 shrink-0 text-right text-xs text-text-faint">
        用了 {option.usage_count} 次
      </span>
      {changed ? (
        <button
          type="button"
          onClick={() => onRename(option, value.trim())}
          className="rounded-md bg-brand px-3 text-sm text-on-brand"
        >
          改名
        </button>
      ) : (
        <button
          type="button"
          onClick={() => onDelete(option)}
          aria-label={`從建議中移除「${option.value}」`}
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
        <EmptyState>還沒有記下任何值。輸入過一次，它就會出現在這裡。</EmptyState>
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

  if (options.isLoading) return <LoadingState label="載入選項中…" />
  if (options.isError) return <ErrorState error={options.error} onRetry={options.refetch} />

  const onRename = (option, value) => {
    const collision = options.data.find(
      (row) => row.kind === option.kind && row.value === value,
    )
    setNotice(
      collision
        ? `已合併到「${value}」，改寫了 ${option.usage_count} 筆資料。`
        : `已改名，改寫了 ${option.usage_count} 筆資料。`,
    )
    rename.mutate({ id: option.id, value })
  }

  const byKind = (kind) => options.data.filter((row) => row.kind === kind)

  return (
    <main className="mx-auto max-w-2xl pb-16">
      <div className="px-4 pt-6">
        <Link to="/lists" className="text-sm text-text-faint no-underline">
          ← 所有清單
        </Link>
        <h1 className="mt-2 mb-1 text-xl font-semibold">常用選項</h1>
        <p className="m-0 text-sm text-text-faint">
          類別、包包、取得地點和車票類型的建議值，從你輸入過的內容記下來。移除建議值不會動到任何資料。
        </p>
      </div>

      {notice && (
        <p className="mx-4 mt-4 rounded-md bg-brand-soft px-3 py-2 text-sm text-brand">
          {notice}
        </p>
      )}

      {Object.entries(LABEL_KIND_LABELS).map(([kind, title]) => (
        <Group
          key={kind}
          title={title}
          options={byKind(kind)}
          onRename={onRename}
          onDelete={(option) => remove.mutate(option.id)}
        />
      ))}
    </main>
  )
}
