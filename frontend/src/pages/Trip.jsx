/**
 * This time: the trip being taken, leg by leg.
 *
 * The sheet's tab, as cards — one per leg, with the booking code large enough
 * to read off a phone at a ticket gate. `/trip` is the current trip and
 * `/trips/:tripId` any other, through the same component. Every field is a
 * cell that commits on Enter or blur; the times, the packing list link and the
 * three ticks are the exceptions, because each has a refusal worth showing.
 */

import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '../api/client'
import { endpoints } from '../api/endpoints'
import { TextCell } from '../components/Cell'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { PriceCell } from '../components/PriceCell'
import { RowMenu } from '../components/RowMenu'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { send, useApiMutation, useApiQuery } from '../hooks/useApiQuery'
import { required } from '../lib/cells'
import { keysFor } from '../lib/keys'
import { BOOKING_LABELS } from '../lib/labels'
import {
  formatArrival,
  formatDuration,
  formatTaipei,
  fromTaipeiInput,
  sortLegs,
  taipeiInputValue,
  tripDateRange,
} from '../lib/trips'

const TRIPS = ['trips']
const INVALIDATE = [TRIPS, ['packing-list'], ['packing-lists'], ['label-options']]
const COPIED_MS = 2000
const BOOKING_FIELDS = ['booked', 'paid', 'collected']

const inputClass = 'rounded-md border border-border bg-canvas px-2 py-1.5 text-sm text-text min-w-0'
const smallButton = 'rounded-md border border-border-strong px-3 text-sm text-text-muted'
const editButton = 'px-1 text-xs text-text-faint hover:text-text'

const hasStatus = (error, status) => error instanceof ApiError && error.status === status

function useTripMutation(mutationFn) {
  return useApiMutation({ invalidate: INVALIDATE, mutationFn })
}

function Field({ label, children }) {
  return (
    <>
      <dt className="self-center text-sm text-text-muted">{label}</dt>
      <dd className="m-0 min-w-0">{children}</dd>
    </>
  )
}

function DeleteMenu({ label, menuLabel, onSelect }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button
        type="button"
        aria-label={menuLabel}
        aria-haspopup="menu"
        onClick={() => setOpen(true)}
        className="px-2 text-text-faint hover:text-text"
        style={{ minHeight: 0 }}
      >
        ⋯
      </button>
      <RowMenu
        open={open}
        onClose={() => setOpen(false)}
        actions={[{ label, danger: true, onSelect }]}
      />
    </>
  )
}

function Problem({ children }) {
  if (!children) return null
  return (
    <p role="alert" className="m-0 mt-1 text-xs text-danger">
      {children}
    </p>
  )
}

/** 訂票代碼: tap to copy, ✎ to edit. The clipboard can refuse, so that is handled. */
function BookingCode({ code, onCommit }) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState('')
  const [copied, setCopied] = useState(null)
  const timer = useRef(null)

  useEffect(() => () => clearTimeout(timer.current), [])

  const flash = (message) => {
    setCopied(message)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setCopied(null), COPIED_MS)
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      flash('已複製')
    } catch {
      flash('無法複製')
    }
  }

  const finish = (save) => {
    setEditing(false)
    const next = text.trim() || null
    if (save && next !== code) onCommit(next)
  }

  if (editing) {
    return (
      <input
        autoFocus
        aria-label="訂票代碼"
        value={text}
        onFocus={(event) => event.target.select()}
        onChange={(event) => setText(event.target.value)}
        onBlur={() => finish(true)}
        onKeyDown={keysFor(
          () => finish(true),
          () => finish(false),
        )}
        className={`${inputClass} w-full font-mono text-2xl tracking-widest`}
      />
    )
  }
  return (
    <div className="flex items-center gap-1">
      {code ? (
        <button
          type="button"
          onClick={copy}
          title="點一下複製"
          className="flex-1 rounded-md border border-border-strong bg-surface-2 px-3 py-2 text-left font-mono text-2xl tracking-widest text-text"
        >
          {code}
          {copied && (
            <span role="status" className="ml-3 font-sans text-sm tracking-normal text-brand">
              {copied}
            </span>
          )}
        </button>
      ) : (
        <span className="flex-1 text-sm text-text-faint">沒有訂票代碼</span>
      )}
      <button
        type="button"
        aria-label="編輯訂票代碼"
        onClick={() => {
          setText(code ?? '')
          setEditing(true)
        }}
        className={editButton}
        style={{ minHeight: 0 }}
      >
        ✎
      </button>
    </div>
  )
}

/** Two datetime-local inputs, read and written in Taipei time. */
function TimesEditor({ leg, onSave, onCancel, problem }) {
  const [departs, setDeparts] = useState(taipeiInputValue(leg.departs_at))
  const [arrives, setArrives] = useState(taipeiInputValue(leg.arrives_at))
  const ready = departs !== '' && arrives !== ''

  return (
    <div className="mt-1">
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="datetime-local"
          aria-label="出發時間"
          value={departs}
          onChange={(event) => setDeparts(event.target.value)}
          className={inputClass}
        />
        <span className="text-text-faint">→</span>
        <input
          type="datetime-local"
          aria-label="抵達時間"
          value={arrives}
          onChange={(event) => setArrives(event.target.value)}
          className={inputClass}
        />
        <button
          type="button"
          disabled={!ready}
          onClick={() =>
            onSave({
              departs_at: fromTaipeiInput(departs),
              arrives_at: fromTaipeiInput(arrives),
            })
          }
          className={smallButton}
        >
          儲存
        </button>
        <button type="button" onClick={onCancel} className={smallButton}>
          取消
        </button>
      </div>
      <Problem>{problem}</Problem>
    </div>
  )
}

/** The link to a packing list, and a select to move it. */
function PackingListLink({ leg, onLink }) {
  const [editing, setEditing] = useState(false)
  const [problem, setProblem] = useState(null)
  const lists = useApiQuery(['packing-lists'], endpoints.packingLists.index(), {
    enabled: editing,
  })

  const choices = []
  if (lists.data) {
    const seen = new Set()
    for (const list of [...lists.data.recent, ...lists.data.saved, ...lists.data.templates]) {
      if (!seen.has(list.id)) {
        seen.add(list.id)
        choices.push(list)
      }
    }
  }

  const choose = async (value) => {
    try {
      await onLink(value === '' ? null : Number(value))
      setProblem(null)
      setEditing(false)
    } catch (caught) {
      setProblem(hasStatus(caught, 409) ? '這份清單已經連到別的行程段' : '發生錯誤')
    }
  }

  return (
    <div className="text-sm">
      <div className="flex items-center gap-1">
        {leg.packing_list_id ? (
          <Link to={`/lists/${leg.packing_list_id}`} className="text-brand">
            打包清單：{leg.packing_list_name}
          </Link>
        ) : (
          <span className="text-text-faint">打包清單：未連結</span>
        )}
        <button
          type="button"
          aria-label="編輯打包清單"
          onClick={() => setEditing(!editing)}
          className={editButton}
          style={{ minHeight: 0 }}
        >
          ✎
        </button>
      </div>
      {editing && (
        <select
          aria-label="連結的打包清單"
          value={leg.packing_list_id ?? ''}
          onChange={(event) => choose(event.target.value)}
          disabled={!lists.data}
          className={`${inputClass} mt-1 w-full sm:w-72`}
        >
          <option value="">（不連結）</option>
          {choices.map((list) => (
            <option key={list.id} value={list.id}>
              {list.name}
            </option>
          ))}
        </select>
      )}
      <Problem>{problem}</Problem>
    </div>
  )
}

function LegCard({ leg, ticketTypes, actions }) {
  const [editingTimes, setEditingTimes] = useState(false)
  const [timesProblem, setTimesProblem] = useState(null)
  const [confirming, setConfirming] = useState(false)
  const patch = (changes) => actions.patchLeg.mutate({ id: leg.id, changes })
  const patchAsync = (changes) => actions.patchLeg.mutateAsync({ id: leg.id, changes })

  const saveTimes = async (changes) => {
    try {
      await patchAsync(changes)
      setTimesProblem(null)
      setEditingTimes(false)
    } catch (caught) {
      setTimesProblem(hasStatus(caught, 422) ? '抵達時間要晚於出發時間' : '發生錯誤')
    }
  }

  return (
    <article className="rounded-md border border-border bg-surface p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <h3 className="m-0 flex flex-wrap items-center text-lg font-semibold">
            <span className="[&_button]:w-auto [&_input]:w-32">
              <TextCell
                value={leg.from_place}
                placeholder="起點"
                onCommit={required((from_place) => patch({ from_place }))}
              />
            </span>
            <span aria-hidden="true">→</span>
            <span className="[&_button]:w-auto [&_input]:w-32">
              <TextCell
                value={leg.to_place}
                placeholder="終點"
                onCommit={required((to_place) => patch({ to_place }))}
              />
            </span>
          </h3>
          <p className="m-0 flex items-center gap-1 text-sm text-text-muted">
            <span>
              {formatTaipei(leg.departs_at)} – {formatArrival(leg.departs_at, leg.arrives_at)} ·{' '}
              {formatDuration(leg.departs_at, leg.arrives_at)}
            </span>
            <button
              type="button"
              aria-label="編輯時間"
              onClick={() => setEditingTimes(!editingTimes)}
              className={editButton}
              style={{ minHeight: 0 }}
            >
              ✎
            </button>
          </p>
          {editingTimes && (
            <TimesEditor
              leg={leg}
              onSave={saveTimes}
              onCancel={() => {
                setEditingTimes(false)
                setTimesProblem(null)
              }}
              problem={timesProblem}
            />
          )}
        </div>
        <DeleteMenu
          label="刪除這段"
          menuLabel={`${leg.from_place} → ${leg.to_place} 的選單`}
          onSelect={() => setConfirming(true)}
        />
      </div>

      <dl className="m-0 mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
        <Field label="車種">
          <TextCell value={leg.service} placeholder="—" onCommit={(service) => patch({ service })} />
        </Field>
        <Field label="車號">
          <TextCell
            value={leg.service_number}
            placeholder="—"
            onCommit={(service_number) => patch({ service_number })}
          />
        </Field>
        <Field label="座位">
          <TextCell value={leg.seat} placeholder="—" onCommit={(seat) => patch({ seat })} />
        </Field>
        <Field label="價錢">
          <PriceCell price={leg.price} onCommit={(price) => patch({ price })} />
        </Field>
        <Field label="車票類型">
          <TextCell
            value={leg.ticket_type}
            placeholder="—"
            options={ticketTypes}
            listId={`ticket-types-${leg.id}`}
            onCommit={(ticket_type) => patch({ ticket_type })}
          />
        </Field>
      </dl>

      <div className="mt-2">
        <BookingCode code={leg.booking_code} onCommit={(booking_code) => patch({ booking_code })} />
      </div>

      <div className="mt-2 flex flex-wrap gap-2">
        {BOOKING_FIELDS.map((field) => (
          <button
            key={field}
            type="button"
            aria-pressed={leg[field]}
            onClick={() => patch({ [field]: !leg[field] })}
            className={`rounded-md px-3 text-sm ${
              leg[field] ? 'bg-brand text-on-brand' : 'bg-surface-2 text-text-muted'
            }`}
            style={{ minHeight: 32 }}
          >
            {leg[field] ? '✓ ' : ''}
            {BOOKING_LABELS[field]}
          </button>
        ))}
      </div>

      <dl className="m-0 mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
        <Field label="備註">
          <TextCell value={leg.notes} placeholder="—" onCommit={(notes) => patch({ notes })} />
        </Field>
      </dl>

      <div className="mt-2">
        <PackingListLink leg={leg} onLink={(packing_list_id) => patchAsync({ packing_list_id })} />
      </div>

      {confirming && (
        <ConfirmDialog
          title={`刪除「${leg.from_place} → ${leg.to_place}」？`}
          body="這一段的訂票資料會一起刪除，連結的打包清單不受影響。"
          confirmLabel="刪除"
          onConfirm={() => {
            setConfirming(false)
            actions.deleteLeg.mutate(leg.id)
          }}
          onCancel={() => setConfirming(false)}
        />
      )}
    </article>
  )
}

function AddLeg({ onAdd }) {
  const [open, setOpen] = useState(false)
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [departs, setDeparts] = useState('')
  const [arrives, setArrives] = useState('')
  const [problem, setProblem] = useState(null)
  const ready = from.trim() && to.trim() && departs && arrives

  const submit = async () => {
    if (!ready) return
    try {
      await onAdd({
        from_place: from.trim(),
        to_place: to.trim(),
        departs_at: fromTaipeiInput(departs),
        arrives_at: fromTaipeiInput(arrives),
      })
      setFrom('')
      setTo('')
      setDeparts('')
      setArrives('')
      setProblem(null)
      setOpen(false)
    } catch (caught) {
      setProblem(hasStatus(caught, 422) ? '抵達時間要晚於出發時間' : '發生錯誤')
    }
  }

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className={`${smallButton} self-start`}>
        + 新增一段
      </button>
    )
  }
  return (
    <div className="rounded-md border border-dashed border-border-strong p-3">
      <div className="flex flex-wrap items-center gap-2">
        <input
          autoFocus
          aria-label="起點"
          placeholder="起點"
          value={from}
          onChange={(event) => setFrom(event.target.value)}
          className={`${inputClass} w-32`}
        />
        <span className="text-text-faint">→</span>
        <input
          aria-label="終點"
          placeholder="終點"
          value={to}
          onChange={(event) => setTo(event.target.value)}
          className={`${inputClass} w-32`}
        />
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <input
          type="datetime-local"
          aria-label="出發時間"
          value={departs}
          onChange={(event) => setDeparts(event.target.value)}
          className={inputClass}
        />
        <span className="text-text-faint">→</span>
        <input
          type="datetime-local"
          aria-label="抵達時間"
          value={arrives}
          onChange={(event) => setArrives(event.target.value)}
          className={inputClass}
        />
      </div>
      <div className="mt-2 flex gap-2">
        <button type="button" disabled={!ready} onClick={submit} className={smallButton}>
          新增
        </button>
        <button
          type="button"
          onClick={() => {
            setOpen(false)
            setProblem(null)
          }}
          className={smallButton}
        >
          取消
        </button>
      </div>
      <Problem>{problem}</Problem>
    </div>
  )
}

/** A name field and + 新增行程. With `onCancel`, Escape and 取消 close it. */
function CreateTrip({ onCreate, onCancel, autoFocus = false, className = 'justify-center' }) {
  const [name, setName] = useState('')
  const submit = () => {
    if (name.trim()) onCreate(name.trim())
  }
  return (
    <div className={`flex flex-wrap items-center gap-2 ${className}`}>
      <input
        autoFocus={autoFocus}
        aria-label="行程名稱"
        placeholder="行程名稱"
        value={name}
        onChange={(event) => setName(event.target.value)}
        onKeyDown={keysFor(submit, onCancel ?? (() => setName('')))}
        className={`${inputClass} w-48`}
      />
      <button type="button" disabled={!name.trim()} onClick={submit} className={smallButton}>
        + 新增行程
      </button>
      {onCancel && (
        <button type="button" onClick={onCancel} className={smallButton}>
          取消
        </button>
      )}
    </div>
  )
}

/**
 * + 新增行程 on a trip's own page. Once any trip exists /trip always shows one,
 * so this is the only way to a second.
 */
function NewTrip({ onCreate }) {
  const [open, setOpen] = useState(false)
  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className={smallButton}>
        + 新增行程
      </button>
    )
  }
  return (
    <CreateTrip
      autoFocus
      className="mt-2 w-full"
      onCreate={onCreate}
      onCancel={() => setOpen(false)}
    />
  )
}

/**
 * Every trip but the one on screen — past and future alike, so not "past".
 * With `onCreate` the section is shown even with no other trips, to hold
 * + 新增行程.
 */
function OtherTrips({ trips, onCreate }) {
  if (trips.length === 0 && !onCreate) return null
  return (
    <section className="mt-10 border-t border-border pt-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="m-0 text-base font-semibold">其他行程</h2>
        {onCreate && <NewTrip onCreate={onCreate} />}
      </div>
      <ul className="m-0 mt-2 list-none p-0">
        {trips.map((trip) => (
          <li key={trip.id}>
            <Link to={`/trips/${trip.id}`} className="flex justify-between gap-3 py-1.5 text-brand">
              <span>{trip.name}</span>
              <span className="text-text-faint tabular-nums">
                {tripDateRange(trip.legs) ?? '沒有行程段'}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}

function TripView({ trip, otherTrips, ticketTypes, actions, onCreateTrip, onDeleted }) {
  const [confirming, setConfirming] = useState(false)
  const legs = sortLegs(trip.legs)
  const patchTrip = (changes) => actions.patchTrip.mutate({ id: trip.id, changes })

  return (
    <>
      <div className="flex items-center justify-between gap-2">
        <h1 className="m-0 min-w-0 flex-1 text-xl font-semibold">
          <TextCell
            value={trip.name}
            placeholder="行程名稱"
            onCommit={required((name) => patchTrip({ name }))}
          />
        </h1>
        <DeleteMenu
          label="刪除行程"
          menuLabel={`${trip.name} 的選單`}
          onSelect={() => setConfirming(true)}
        />
      </div>
      <TextCell value={trip.notes} placeholder="備註" onCommit={(notes) => patchTrip({ notes })} />

      <div className="mt-4 flex flex-col gap-3">
        {legs.length === 0 && <EmptyState>這個行程還沒有任何一段。</EmptyState>}
        {legs.map((leg) => (
          <LegCard key={leg.id} leg={leg} ticketTypes={ticketTypes} actions={actions} />
        ))}
        <AddLeg onAdd={(payload) => actions.addLeg.mutateAsync({ tripId: trip.id, payload })} />
      </div>

      <OtherTrips trips={otherTrips} onCreate={onCreateTrip} />

      {confirming && (
        <ConfirmDialog
          title={`刪除「${trip.name}」？`}
          body="這個行程和它所有的行程段都會一起刪除，連結的打包清單不受影響。"
          confirmLabel="刪除"
          onConfirm={() => {
            setConfirming(false)
            actions.deleteTrip.mutate(trip.id, { onSuccess: onDeleted })
          }}
          onCancel={() => setConfirming(false)}
        />
      )}
    </>
  )
}

export default function Trip() {
  const { tripId } = useParams()
  const navigate = useNavigate()

  const trip = useApiQuery(
    tripId ? [...TRIPS, 'detail', tripId] : [...TRIPS, 'current'],
    tripId ? endpoints.trips.detail(tripId) : endpoints.trips.current(),
    // A 404 is an answer (no current trip), not a failure worth retrying.
    { retry: (count, error) => !hasStatus(error, 404) && count < 1 },
  )
  const all = useApiQuery([...TRIPS, 'index'], endpoints.trips.index())
  const options = useApiQuery(['label-options'], endpoints.labelOptions.index())

  const createTrip = useTripMutation((payload) => send(endpoints.trips.index(), 'POST', payload))
  const patchTrip = useTripMutation(({ id, changes }) =>
    send(endpoints.trips.detail(id), 'PATCH', changes),
  )
  const deleteTrip = useTripMutation((id) => send(endpoints.trips.detail(id), 'DELETE'))
  const addLeg = useTripMutation(({ tripId: id, payload }) =>
    send(endpoints.trips.legs(id), 'POST', payload),
  )
  const patchLeg = useTripMutation(({ id, changes }) =>
    send(endpoints.trips.leg(id), 'PATCH', changes),
  )
  const deleteLeg = useTripMutation((id) => send(endpoints.trips.leg(id), 'DELETE'))

  const openNewTrip = (name) =>
    createTrip.mutate(
      { name },
      // A trip with no legs is never the current one, so the new trip is
      // opened by its own address.
      { onSuccess: (created) => navigate(`/trips/${created.id}`) },
    )

  if (trip.isLoading) return <LoadingState label="載入行程中…" />

  const shell = (children) => (
    <main className="mx-auto max-w-4xl overflow-x-hidden px-4 pb-16 pt-6">{children}</main>
  )

  if (trip.isError && !hasStatus(trip.error, 404)) {
    return <ErrorState error={trip.error} onRetry={trip.refetch} />
  }
  if (trip.isError) {
    if (tripId) return shell(<EmptyState>找不到這個行程。</EmptyState>)
    return shell(
      <>
        <h1 className="m-0 text-xl font-semibold">This time</h1>
        <EmptyState
          action={<CreateTrip onCreate={openNewTrip} />}
        >
          還沒有行程。
        </EmptyState>
        <OtherTrips trips={all.data ?? []} />
      </>,
    )
  }

  const ticketTypes = (options.data || [])
    .filter((row) => row.kind === 'ticket_type')
    .map((row) => row.value)
  const otherTrips = (all.data ?? []).filter((other) => other.id !== trip.data.id)
  const actions = { patchTrip, deleteTrip, addLeg, patchLeg, deleteLeg }

  return shell(
    <TripView
      key={trip.data.id}
      trip={trip.data}
      otherTrips={otherTrips}
      ticketTypes={ticketTypes}
      actions={actions}
      onCreateTrip={openNewTrip}
      onDeleted={() => navigate('/trip')}
    />,
  )
}
