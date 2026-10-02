/**
 * 行程: every trip, on four tabs - 一般, 範本, 保存 and 自動保存（n / 10）.
 *
 * Compact on purpose: a card per trip with one line per leg, enough to tell
 * trips apart and see when each one leaves. The whole trip - booking codes,
 * prices, the packing list - is one click away on /trips/:id, the way a list
 * is on /lists/:id. 刪除模式 lives in the 自動保存 tab, where old trips pile up.
 */

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { endpoints } from '../api/endpoints'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { IndexTabs } from '../components/IndexTabs'
import { ErrorState, LoadingState } from '../components/States'
import { send, useApiMutation, useApiQuery } from '../hooks/useApiQuery'
import { keysFor } from '../lib/keys'
import { AUTO_SAVE_LIMIT, TABS, autofillName, isAutoSaved, tabCounts } from '../lib/kinds'
import { KIND_LABELS, USAGE_LABELS } from '../lib/labels'
import { firstLine, legSummary, needsStartDate, sortLegs } from '../lib/trips'

const INDEX = ['trips', 'index']
const inputClass = 'rounded-md border border-border bg-canvas px-2 py-1.5 text-sm text-text min-w-0'
const smallButton = 'rounded-md border border-border-strong px-3 text-sm text-text-muted'
const badge = 'shrink-0 rounded-sm bg-surface-2 px-2 text-xs font-normal text-text-muted'

const EMPTY = {
  free: '目前沒有一般行程。按「+ 新增行程」開始。',
  template: '按行程的「當作範本」或新增一份範本，之後的新行程可以從它開始。',
  saved: '在行程的選單按「保存」，它就不會被自動刪除。',
  auto_saved: '把一般行程的狀態設為「過去使用」，它會自動保存在這裡。',
}

/**
 * A name, 一般 or 範本, an optional 從範本 and + 新增行程. Picking a template
 * fills the name unless one was typed. A template with legs needs a 出發日期,
 * the Taipei day its first leg moves to. `pending` holds 建立 while a create
 * is in flight, so a second click cannot make a second trip.
 */
function CreateTrip({ templates, pending, failed, onCreate, onCancel }) {
  const [name, setName] = useState('')
  const [fill, setFill] = useState('')
  const [kind, setKind] = useState('free')
  const [templateId, setTemplateId] = useState('')
  const [startDate, setStartDate] = useState('')
  const template = templates.find((row) => String(row.id) === templateId)
  const dateNeeded = template ? needsStartDate(template) : false
  const ready = Boolean(name.trim()) && (!dateNeeded || Boolean(startDate))

  const pickTemplate = (id) => {
    const source = templates.find((row) => String(row.id) === id)
    const next = autofillName({ current: name, lastFill: fill, source: source?.name ?? null })
    setTemplateId(id)
    setName(next.name)
    setFill(next.fill)
  }
  const submit = () => {
    if (!ready || pending) return
    const payload = { name: name.trim(), kind }
    if (template) {
      payload.copy_from_id = template.id
      if (dateNeeded) payload.start_date = startDate
    }
    onCreate(payload)
  }

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 px-4">
      <input
        autoFocus
        aria-label="行程名稱"
        placeholder="行程名稱"
        value={name}
        onChange={(event) => setName(event.target.value)}
        onKeyDown={keysFor(submit, onCancel)}
        className={`${inputClass} w-48`}
      />
      <select
        aria-label="類型"
        value={kind}
        onChange={(event) => setKind(event.target.value)}
        className={inputClass}
      >
        <option value="free">{KIND_LABELS.free}</option>
        <option value="template">{KIND_LABELS.template}</option>
      </select>
      {templates.length > 0 && (
        <select
          aria-label="從範本"
          value={templateId}
          onChange={(event) => pickTemplate(event.target.value)}
          className={inputClass}
        >
          <option value="">不使用範本</option>
          {templates.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </select>
      )}
      {dateNeeded && (
        <input
          type="date"
          aria-label="出發日期"
          value={startDate}
          onChange={(event) => setStartDate(event.target.value)}
          className={inputClass}
        />
      )}
      <button
        type="button"
        disabled={!ready || pending}
        onClick={submit}
        className={`${smallButton} disabled:opacity-40`}
      >
        建立
      </button>
      <button type="button" onClick={onCancel} className={smallButton}>
        取消
      </button>
      {failed && (
        <p role="alert" className="m-0 w-full text-sm text-danger">
          無法建立行程，請再試一次。
        </p>
      )}
    </div>
  )
}

/**
 * One trip: name, a 狀態 badge on 一般 and 自動保存, one line per leg. 保存
 * and 自動保存 cards add the first line of 保存備註.
 */
function TripCard({ trip, selecting, selected, onToggle }) {
  const legs = sortLegs(trip.legs)
  const note = (trip.kind === 'saved' || isAutoSaved(trip)) && firstLine(trip.archive_note)
  return (
    <li className="flex items-start gap-3 border-b border-border px-4 py-3">
      {selecting && (
        <input
          type="checkbox"
          className="mt-1 size-4"
          aria-label={`選取「${trip.name}」`}
          checked={selected}
          onChange={onToggle}
        />
      )}
      <Link to={`/trips/${trip.id}`} className="min-w-0 flex-1 text-text no-underline">
        <span className="flex items-center justify-between gap-2">
          <span className="min-w-0 font-semibold">{trip.name}</span>
          {trip.kind === 'free' && <span className={badge}>{USAGE_LABELS[trip.usage]}</span>}
        </span>
        {note && <span className="block text-xs text-text-faint">{note}</span>}
        {legs.length === 0 ? (
          <span className="block text-sm text-text-faint">沒有行程段</span>
        ) : (
          legs.map((leg) => (
            <span key={leg.id} className="block text-sm tabular-nums text-text-muted">
              {legSummary(leg)}
            </span>
          ))
        )}
      </Link>
    </li>
  )
}

/**
 * One tab's cards. On 自動保存 it holds 刪除模式: a checkbox per card, 全選,
 * and 刪除所選（n）, confirmed once for the whole selection.
 */
function TripPanel({ tab, trips, deleting, deleteFailed, onBulkDelete }) {
  const [selecting, setSelecting] = useState(false)
  const [selected, setSelected] = useState(new Set())
  const [confirming, setConfirming] = useState(false)
  const deletable = tab === 'auto_saved' && trips.length > 0
  const chosen = trips.filter((trip) => selected.has(trip.id))
  const toggle = (id) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelected(next)
  }

  if (trips.length === 0) {
    return <p className="px-4 py-6 text-center text-sm text-text-muted">{EMPTY[tab]}</p>
  }
  return (
    <>
      {deletable && (
        <div className="flex flex-wrap items-center gap-2 px-4 pt-3">
          <button
            type="button"
            className={smallButton}
            onClick={() => {
              setSelecting(!selecting)
              setSelected(new Set())
            }}
          >
            {selecting ? '完成' : '刪除模式'}
          </button>
          {selecting && (
            <>
              <label className="flex items-center gap-1 text-sm text-text-muted">
                <input
                  type="checkbox"
                  className="size-4"
                  checked={chosen.length === trips.length}
                  onChange={(event) =>
                    setSelected(event.target.checked ? new Set(trips.map((t) => t.id)) : new Set())
                  }
                />
                全選
              </label>
              <button
                type="button"
                disabled={chosen.length === 0 || deleting}
                onClick={() => setConfirming(true)}
                className="rounded-md border border-danger px-3 text-sm text-danger disabled:opacity-40"
              >
                刪除所選（{chosen.length}）
              </button>
            </>
          )}
          {deleteFailed && (
            <p role="alert" className="m-0 w-full text-sm text-danger">
              無法刪除，請再試一次。
            </p>
          )}
        </div>
      )}
      <ul className="m-0 list-none p-0">
        {trips.map((trip) => (
          <TripCard
            key={trip.id}
            trip={trip}
            selecting={selecting}
            selected={selected.has(trip.id)}
            onToggle={() => toggle(trip.id)}
          />
        ))}
      </ul>
      {confirming && (
        <ConfirmDialog
          title={`刪除 ${chosen.length} 個行程？`}
          body={`${chosen.map((trip) => `「${trip.name}」`).join('、')}和它們所有的行程段都會一起刪除，連結的打包清單不受影響。`}
          confirmLabel="刪除"
          onConfirm={() => {
            setConfirming(false)
            onBulkDelete(chosen.map((trip) => trip.id), () => {
              setSelected(new Set())
              setSelecting(false)
            })
          }}
          onCancel={() => setConfirming(false)}
        />
      )}
    </>
  )
}

export default function Trips() {
  const navigate = useNavigate()
  const index = useApiQuery(INDEX, endpoints.trips.index())
  const [creating, setCreating] = useState(false)
  // A deleted trip's linked list loses its leg, and with it the date the leg
  // gave it, so the packing-list queries refresh too.
  const invalidate = [['trips'], ['packing-lists'], ['packing-list']]

  const create = useApiMutation({
    invalidate,
    mutationFn: (payload) => send(endpoints.trips.index(), 'POST', payload),
    // What the copy could not carry rides along in the navigation state.
    onSuccess: (created) =>
      navigate(`/trips/${created.id}`, { state: { unlinked: created.unlinked_from } }),
  })
  const bulkDelete = useApiMutation({
    invalidate,
    mutationFn: (ids) => send(endpoints.trips.bulkDelete(), 'POST', { ids }),
  })

  if (index.isLoading) return <LoadingState label="載入行程中…" />
  if (index.isError) return <ErrorState error={index.error} onRetry={index.refetch} />

  return (
    <main className="mx-auto max-w-4xl pb-16">
      <div className="flex items-center justify-between px-4 pt-6">
        <h1 className="m-0 text-xl font-semibold">行程</h1>
        {!creating && (
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="rounded-md bg-brand px-4 text-sm font-medium text-on-brand"
          >
            + 新增行程
          </button>
        )}
      </div>
      {creating && (
        <CreateTrip
          templates={index.data.templates}
          pending={create.isPending}
          failed={create.isError}
          onCreate={create.mutate}
          onCancel={() => setCreating(false)}
        />
      )}

      <IndexTabs counts={tabCounts(index.data, AUTO_SAVE_LIMIT.trips)}>
        {(tab) => (
          <TripPanel
            key={tab}
            tab={tab}
            trips={index.data[TABS.find((t) => t.key === tab).shelf]}
            deleting={bulkDelete.isPending}
            deleteFailed={bulkDelete.isError}
            onBulkDelete={(ids, onSuccess) => bulkDelete.mutate(ids, { onSuccess })}
          />
        )}
      </IndexTabs>
    </main>
  )
}
