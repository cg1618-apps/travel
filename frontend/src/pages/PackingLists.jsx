/**
 * Every list, on four tabs: 一般, 範本, 保存 and 自動保存（n / 5）.
 *
 * Tabs rather than stacked sections, so every list is in exactly one place
 * and the counts say where without scrolling. Each row carries its own 狀態,
 * 保存 and 當作範本; 過去使用 into a full 自動保存 is the one change that asks
 * first, naming the list it would drop.
 */

import { useState } from 'react'
import { Link } from 'react-router-dom'

import { endpoints } from '../api/endpoints'
import { EvictDialog } from '../components/EvictDialog'
import { IndexTabs } from '../components/IndexTabs'
import { KindControls } from '../components/KindControls'
import { ErrorState, LoadingState } from '../components/States'
import { send, useApiMutation, useApiQuery } from '../hooks/useApiQuery'
import {
  AUTO_SAVE_LIMIT, TABS, autofillName, badgeFor, everyRow, tabCounts, templateName,
} from '../lib/kinds'
import { KIND_LABELS, LEG_LABELS } from '../lib/labels'
import { departureLabel } from '../lib/timing'
import { firstLine } from '../lib/trips'

const INDEX_KEY = ['packing-lists']

// `fill` is the name the copy select last wrote, so a typed name is kept.
const BLANK = { name: '', departure_at: '', copy_from_id: '', kind: 'free', fill: '' }

const EMPTY = {
  free: '目前沒有一般清單。從上面新增一份。',
  template: '按「當作範本」或新增一份範本，之後的新清單可以從它開始。',
  saved: '在清單上勾選「保存」，它就不會被自動刪除。',
  auto_saved: '把一般清單的狀態設為「過去使用」，它會自動保存在這裡。',
}

function Table({ rows, empty, onPatch, onMakeTemplate }) {
  if (rows.length === 0) {
    return <p className="px-4 py-6 text-center text-sm text-text-muted">{empty}</p>
  }
  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr className="border-b border-border bg-surface-2 text-xs tracking-wide text-text-muted">
          <th scope="col" className="px-4 py-2 text-left font-semibold">
            清單
          </th>
          <th scope="col" className="w-28 px-2 py-2 text-left font-semibold">
            出發
          </th>
          <th scope="col" className="w-28 px-2 py-2 text-left font-semibold">
            已處理
          </th>
          <th scope="col" className="px-2 py-2" />
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
              {row.archive_note && (
                <span className="block text-xs text-text-faint">{firstLine(row.archive_note)}</span>
              )}
            </td>
            <td className="px-2 py-2 text-text-muted">{departureLabel(row.departure_at, new Date())}</td>
            <td className="px-2 py-2 tabular-nums text-text-muted">
              {row.settled_count} / {row.item_count}
            </td>
            <td className="px-2 py-2">
              <KindControls
                row={row}
                noun="清單"
                onPatch={(changes) => onPatch(row, changes)}
                onMakeTemplate={() => onMakeTemplate(row)}
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function PackingLists() {
  const indexQuery = useApiQuery(INDEX_KEY, endpoints.packingLists.index())
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState(BLANK)
  const [refusal, setRefusal] = useState(null) // { id, changes } of a refused 過去使用
  const [madeTemplate, setMadeTemplate] = useState(null)

  const create = useApiMutation({
    invalidate: [INDEX_KEY],
    mutationFn: (payload) => send(endpoints.packingLists.index(), 'POST', payload),
    onSuccess: () => {
      setDraft(BLANK)
      setOpen(false)
    },
  })
  const makeTemplate = useApiMutation({
    invalidate: [INDEX_KEY],
    mutationFn: (row) =>
      send(endpoints.packingLists.index(), 'POST', {
        name: templateName(row.name), kind: 'template', copy_from_id: row.id,
      }),
    onSuccess: (created) => setMadeTemplate(created),
  })
  const patch = useApiMutation({
    invalidate: [INDEX_KEY],
    mutationFn: ({ id, changes }) => send(endpoints.packingLists.detail(id), 'PATCH', changes),
    onError: (error, variables) => {
      // A 409 is a decision to put to the person, not a failure to report.
      if (error.status === 409) setRefusal(variables)
    },
  })

  if (indexQuery.isLoading) return <LoadingState label="載入清單中…" />
  if (indexQuery.isError) return <ErrorState error={indexQuery.error} onRetry={indexQuery.refetch} />

  const index = indexQuery.data
  const copyable = everyRow(index)
  const onPatch = (row, changes) => patch.mutate({ id: row.id, changes })

  const payload = () => ({
    name: draft.name.trim(),
    departure_at: draft.departure_at || null,
    copy_from_id: draft.copy_from_id ? Number(draft.copy_from_id) : null,
    kind: draft.kind,
  })

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
              類型
              <select
                value={draft.kind}
                onChange={(event) => setDraft({ ...draft, kind: event.target.value })}
                className="mt-1 block rounded-md border border-border bg-canvas px-3 py-2 text-base text-text"
              >
                <option value="free">{KIND_LABELS.free}</option>
                <option value="template">{KIND_LABELS.template}</option>
              </select>
            </label>
            <label className="text-xs text-text-faint">
              從哪份清單複製項目
              <select
                value={draft.copy_from_id}
                onChange={(event) => {
                  const id = event.target.value
                  const source = copyable.find((row) => String(row.id) === id)
                  const { name, fill } = autofillName({
                    current: draft.name, lastFill: draft.fill, source: source?.name ?? null,
                  })
                  setDraft({ ...draft, copy_from_id: id, name, fill })
                }}
                className="mt-1 block rounded-md border border-border bg-canvas px-3 py-2 text-base text-text"
              >
                <option value="">空白開始</option>
                {copyable.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.name}
                    {badgeFor(row) ? `（${badgeFor(row)}）` : ''}
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
          {create.isError && <p className="mt-2 text-sm text-danger">無法建立清單，請再試一次。</p>}
        </form>
      )}

      {madeTemplate && (
        <p className="mx-4 mt-4 rounded-md bg-surface-2 px-3 py-2 text-sm">
          已建立範本 <Link to={`/lists/${madeTemplate.id}`}>{madeTemplate.name}</Link>。
          <button type="button" onClick={() => setMadeTemplate(null)} className="ml-2 text-text-muted">
            知道了
          </button>
        </p>
      )}
      <IndexTabs counts={tabCounts(index, AUTO_SAVE_LIMIT.lists)}>
        {(tab) => (
          <Table
            rows={index[TABS.find((t) => t.key === tab).shelf]}
            empty={EMPTY[tab]}
            onPatch={onPatch}
            onMakeTemplate={makeTemplate.mutate}
          />
        )}
      </IndexTabs>

      {refusal && (
        <EvictDialog
          noun="一份清單"
          body={`自動保存最多 ${AUTO_SAVE_LIMIT.lists} 份清單。設為過去使用會刪除最舊的：`}
          evicting={index.evict_next}
          onSaveInstead={async () => {
            await Promise.all(index.evict_next.map((row) =>
              patch.mutateAsync({ id: row.id, changes: { kind: 'saved' } })))
            setRefusal(null)
            patch.mutate(refusal)
          }}
          onConfirm={() => {
            setRefusal(null)
            patch.mutate({ ...refusal, changes: { ...refusal.changes, evict_confirmed: true } })
          }}
          onCancel={() => setRefusal(null)}
        />
      )}
    </main>
  )
}
