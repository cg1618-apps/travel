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
 *
 * The header carries the list's 狀態, 保存 and 當作範本, the same controls as
 * its row on /lists, with 備註 and - where it matters - 保存備註 beneath.
 */

import { useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { endpoints } from '../api/endpoints'
import { TextCell } from '../components/Cell'
import { Checklist } from '../components/Checklist'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { DeleteMenu } from '../components/DeleteMenu'
import { EvictDialog } from '../components/EvictDialog'
import { Grid } from '../components/Grid'
import { KindControls } from '../components/KindControls'
import { ErrorState, LoadingState } from '../components/States'
import { send, useApiMutation, useApiQuery } from '../hooks/useApiQuery'
import { required } from '../lib/cells'
import { AUTO_SAVE_LIMIT, badgeFor, isAutoSaved } from '../lib/kinds'
import { leavingText, progressParts } from '../lib/listHeader'

const VIEW_STORAGE_KEY = 'travel.packing.view'

const badge = 'shrink-0 rounded-sm bg-surface-2 px-2 text-xs text-text-muted'

const RESET_BODY =
  '所有已打包的項目會改回未打包，已打包數量歸零，Double Check 改回未確認。不需打包的項目不變。'

const DELETE_BODY =
  '這份清單和它所有的項目都會一起刪除。連結到它的行程段會保留，只是不再連結清單。'

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
 * from a 行程 leg is only shown — it is changed on the leg.
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
  const navigate = useNavigate()
  const key = useMemo(() => ['packing-list', listId], [listId])
  const list = useApiQuery(key, endpoints.packingLists.detail(listId))
  const options = useApiQuery(['label-options'], endpoints.labelOptions.index())

  const [view, setView] = useState(initialView)
  const [confirmingReset, setConfirmingReset] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  // A refused 過去使用: the changes to retry once the person has decided.
  const [refusal, setRefusal] = useState(null)

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
  const addMany = useApiMutation({
    invalidate,
    mutationFn: (rows) => send(endpoints.packingLists.bulkCreate(listId), 'POST', { items: rows }),
  })
  // Optimistic: a dropped row stays where it was dropped rather than jumping
  // back for the round trip. The response is the list itself, so it replaces
  // the cache; a refusal puts the server's order back.
  const queryClient = useQueryClient()
  const reorder = useApiMutation({
    mutationFn: (itemIds) => send(endpoints.packingLists.order(listId), 'PUT', { item_ids: itemIds }),
    onMutate: (itemIds) => {
      queryClient.setQueryData(key, (current) =>
        current && {
          ...current,
          items: current.items.map((item) => ({ ...item, position: itemIds.indexOf(item.id) })),
        },
      )
    },
    onSuccess: (updated) => queryClient.setQueryData(key, updated),
    onError: () => queryClient.invalidateQueries({ queryKey: key }),
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
    onError: (error, changes) => {
      // A 409 is a decision to put to the person, not a failure to report.
      if (error.status === 409) setRefusal(changes)
    },
  })
  // The index is read only to name what a full 自動保存 would drop.
  const lists = useApiQuery(['packing-lists'], endpoints.packingLists.index(), {
    enabled: Boolean(refusal),
  })
  // Lists saved from the dialog: not this list's own PATCH, so a 409 here
  // (there is none for 保存) never opens a second dialog.
  const saveList = useApiMutation({
    invalidate: [['packing-lists']],
    mutationFn: (id) => send(endpoints.packingLists.detail(id), 'PATCH', { kind: 'saved' }),
  })
  const makeTemplate = useApiMutation({
    invalidate: [['packing-lists']],
    mutationFn: () =>
      send(endpoints.packingLists.index(), 'POST', {
        name: list.data.name,
        kind: 'template',
        copy_from_id: list.data.id,
      }),
    onSuccess: (created) => navigate(`/lists/${created.id}`),
  })
  // Not this list's own key: refetching a list that was just deleted is a 404
  // on the screen being left. The trips refresh because a leg loses its link.
  const removeList = useApiMutation({
    invalidate: [['packing-lists'], ['trips']],
    mutationFn: () => send(endpoints.packingLists.detail(listId), 'DELETE'),
    onSuccess: () => navigate('/lists'),
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
        <Link to="/lists" className="text-sm text-text-faint no-underline">
          ← 所有清單
        </Link>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
          <div className="flex min-w-0 flex-1 items-center gap-1">
            <h1 className="m-0 min-w-0 flex-1 text-xl font-semibold">
              <TextCell
                value={list.data.name}
                placeholder="清單名稱"
                onCommit={required((name) => patchList.mutate({ name }))}
              />
            </h1>
            <DeleteMenu
              label="刪除清單"
              menuLabel={`${list.data.name} 的選單`}
              onSelect={() => setConfirmingDelete(true)}
            />
          </div>
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
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {badgeFor(list.data) && <span className={badge}>{badgeFor(list.data)}</span>}
          <KindControls
            row={list.data}
            noun="清單"
            onPatch={(changes) => patchList.mutate(changes)}
            onMakeTemplate={() => makeTemplate.mutate()}
          />
        </div>
        <TextCell
          value={list.data.notes}
          placeholder="備註"
          onCommit={(notes) => patchList.mutate({ notes })}
        />
        {(list.data.kind === 'saved' || isAutoSaved(list.data) || list.data.archive_note) && (
          <TextCell
            value={list.data.archive_note}
            placeholder="保存備註"
            onCommit={(archive_note) => patchList.mutate({ archive_note })}
          />
        )}
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
          <>
            {(addMany.isError || reorder.isError) && (
              <p role="alert" className="mx-4 mb-2 text-sm text-danger">
                {addMany.isError ? '新增失敗，輸入的列還在，請再試一次。' : '排序沒有儲存，已還原。'}
              </p>
            )}
            <Grid
              items={items}
              categories={values('category')}
              locations={values('location')}
              adding={addMany.isPending}
              onAddMany={(rows) => addMany.mutateAsync(rows)}
              onReorder={reorder.mutate}
              {...handlers}
            />
          </>
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

      {/* Only once the index is freshly read: a stale `evict_next` would name,
          and offer to save, a list that is not the one about to go. */}
      {refusal && lists.isSuccess && !lists.isFetching && (
        <EvictDialog
          noun="一份清單"
          body={`自動保存最多 ${AUTO_SAVE_LIMIT.lists} 份清單。設為過去使用會刪除最舊的：`}
          evicting={lists.data.evict_next}
          onSaveInstead={async () => {
            // Save what would go, then retry unconfirmed: the retry succeeds
            // because there is room, not because it was forced. A rejection
            // closes the dialog; the refetch shows the actual state.
            const changes = refusal
            setRefusal(null)
            try {
              await Promise.all(lists.data.evict_next.map((row) => saveList.mutateAsync(row.id)))
              patchList.mutate(changes)
            } catch {
              // Nothing to retry: the save failed, so there is still no room.
            }
          }}
          onConfirm={() => {
            setRefusal(null)
            patchList.mutate({ ...refusal, evict_confirmed: true })
          }}
          onCancel={() => setRefusal(null)}
        />
      )}

      {confirmingDelete && (
        <ConfirmDialog
          title={`刪除「${list.data.name}」？`}
          body={DELETE_BODY}
          confirmLabel="刪除"
          onConfirm={() => {
            setConfirmingDelete(false)
            removeList.mutate()
          }}
          onCancel={() => setConfirmingDelete(false)}
        />
      )}
    </main>
  )
}
