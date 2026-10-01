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
import { LEG_LABELS } from '../lib/labels'
import { departureLabel } from '../lib/timing'

const INDEX_KEY = ['packing-lists']

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
            <tr className="border-y border-border bg-surface-2 text-xs tracking-wide text-text-muted">
              <th scope="col" className="px-4 py-2 text-left font-semibold">
                清單
              </th>
              <th scope="col" className="w-28 px-2 py-2 text-left font-semibold">
                出發
              </th>
              <th scope="col" className="w-28 px-2 py-2 text-left font-semibold">
                已處理
              </th>
              <th scope="col" className="w-16 px-2 py-2 text-center font-semibold">
                保存
              </th>
              <th scope="col" className="w-20 px-2 py-2 text-center font-semibold">
                範本
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
                    <span className="ml-2 text-xs text-text-faint">{LEG_LABELS[row.leg]}</span>
                  )}
                </td>
                <td className="px-2 py-2 text-text-muted">{departureLabel(row.departure_at, new Date())}</td>
                <td className="px-2 py-2 tabular-nums text-text-muted">
                  {row.settled_count} / {row.item_count}
                </td>
                <td className="px-2 py-2 text-center">
                  <input
                    type="checkbox"
                    checked={row.saved}
                    onChange={(event) => onFlag(row, { saved: event.target.checked })}
                    aria-label={`保存「${row.name}」，不受三份清單的上限影響`}
                    title="保存這份清單，不受三份清單的上限影響"
                    className="size-4 align-middle"
                  />
                </td>
                <td className="px-2 py-2 text-center">
                  <input
                    type="checkbox"
                    checked={row.template}
                    onChange={(event) => onFlag(row, { template: event.target.checked })}
                    aria-label={`把「${row.name}」當作新清單的範本`}
                    title="新清單可以從這份開始"
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
  // Which 409 is on screen: creating a list, or un-saving (or un-templating)
  // one, which moves it back under the cap. Each is retried
  // confirmed differently, and says so in its own words.
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
      if (error.status === 409) setRefusal({ kind: 'create' })
    },
  })

  const flag = useApiMutation({
    invalidate: [INDEX_KEY],
    mutationFn: ({ id, changes }) =>
      send(endpoints.packingLists.detail(id), 'PATCH', changes),
    onError: (error, variables) => {
      if (error.status === 409) setRefusal({ kind: 'unsave', ...variables })
    },
  })

  if (index.isLoading) return <LoadingState label="載入清單中…" />
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
        <h1 className="m-0 text-xl font-semibold">打包清單</h1>
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="rounded-md bg-brand px-4 text-sm font-medium text-on-brand"
        >
          {open ? '取消' : '+ 新增清單'}
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
              名稱
              <input
                autoFocus
                value={draft.name}
                onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                placeholder="札幌"
                className="mt-1 block w-full rounded-md border border-border bg-canvas px-3 py-2 text-base text-text"
              />
            </label>
            <label className="text-xs text-text-faint">
              出發日期
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
              從哪份清單複製項目
              <select
                value={draft.copy_from_id}
                onChange={(event) =>
                  setDraft({ ...draft, copy_from_id: event.target.value })
                }
                className="mt-1 block rounded-md border border-border bg-canvas px-3 py-2 text-base text-text"
              >
                <option value="">空白開始</option>
                {copyable.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.name}
                    {row.template ? '（範本）' : ''}
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
            建立
          </button>
          {create.isError && create.error.status !== 409 && (
            <p className="mt-2 text-sm text-danger">無法建立清單，請再試一次。</p>
          )}
        </form>
      )}

      <Table
        title="進行中"
        count={`${recent.length} / 3`}
        rows={recent}
        empty="目前沒有進行中的清單。從上面新增一份。"
        onFlag={onFlag}
      />
      <Table
        title="已保存"
        rows={saved}
        empty="在清單上勾選「保存」，它就不會被取代。"
        onFlag={onFlag}
      />
      <Table
        title="範本"
        rows={templates}
        empty="在清單上勾選「範本」，之後的新清單可以從它開始。"
        onFlag={onFlag}
      />

      {refusal?.kind === 'create' && (
        <EvictDialog
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
      {refusal?.kind === 'unsave' && (
        <EvictDialog
          body="已有 3 份進行中的清單。讓這份清單回到進行中會刪除最舊的："
          confirmLabel="刪除並繼續"
          evicting={evictNext}
          onConfirm={() => {
            setRefusal(null)
            flag.mutate({ id: refusal.id, changes: { ...refusal.changes, evict_confirmed: true } })
          }}
          onCancel={() => setRefusal(null)}
        />
      )}
    </main>
  )
}
