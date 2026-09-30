/**
 * Transportation: every route, its ways of making it, and when they leave.
 *
 * The sheet's tab, kept as a place to edit in place — every field is a cell
 * that commits on Enter or blur and reverts on Escape, with no Save button.
 * Departures are chips under 平日 and 假日, sorted into 早/中/下午/晚 by the
 * clock, with the next one from now picked out.
 */

import { useEffect, useState } from 'react'

import { ApiError } from '../api/client'
import { endpoints } from '../api/endpoints'
import { TextCell } from '../components/Cell'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { PriceCell } from '../components/PriceCell'
import { RowMenu } from '../components/RowMenu'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { send, useApiMutation, useApiQuery } from '../hooks/useApiQuery'
import {
  BUCKETS,
  formatDeparture,
  groupByBucket,
  nextDeparture,
  parseDepartureInput,
} from '../lib/departures'
import { keysFor } from '../lib/keys'
import { ADVANCE_TICKET_LABELS, BUCKET_LABELS, DAY_TYPE_LABELS } from '../lib/labels'
import { DAY_TYPES, groupByDayType } from '../lib/transport'

const KEY = ['transport-routes']
const REFRESH_MS = 60_000

const inputClass =
  'rounded-md border border-border bg-canvas px-2 py-1.5 text-sm text-text min-w-0'
const smallButton = 'rounded-md border border-border-strong px-3 text-sm text-text-muted'

/** The clock the next-departure marker reads, moved on once a minute. */
function useNow() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), REFRESH_MS)
    return () => clearInterval(timer)
  }, [])
  return now
}

/** Every write on this page refreshes the one query the page reads. */
function useTransportMutation(mutationFn) {
  return useApiMutation({ invalidate: [KEY], mutationFn })
}

/** Shared by every cell that cannot be blank: an emptied cell keeps its value. */
const required = (commit) => (value) => {
  if (value) commit(value)
}

/** A link that opens in a new tab once set, with a ✎ to change where it goes. */
function LinkField({ label, url, onCommit }) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState('')

  const finish = (save) => {
    setEditing(false)
    const next = text.trim() || null
    if (save && next !== url) onCommit(next)
  }

  if (editing) {
    return (
      <input
        autoFocus
        type="url"
        aria-label={`${label}網址`}
        placeholder="https://"
        value={text}
        onChange={(event) => setText(event.target.value)}
        onBlur={() => finish(true)}
        onKeyDown={keysFor(
          () => finish(true),
          () => finish(false),
        )}
        className={`${inputClass} w-56 max-w-full`}
      />
    )
  }
  return (
    <span className="inline-flex items-center gap-1 text-sm">
      {url ? (
        <a href={url} target="_blank" rel="noreferrer" className="text-brand">
          {label}
        </a>
      ) : (
        <span className="text-text-faint">{label}</span>
      )}
      <button
        type="button"
        aria-label={`編輯${label}`}
        onClick={() => {
          setText(url ?? '')
          setEditing(true)
        }}
        className="px-1 text-xs text-text-faint hover:text-text"
        style={{ minHeight: 0 }}
      >
        ✎
      </button>
    </span>
  )
}

function Chip({ departure, isNext, onDelete }) {
  const irregular = departure.irregular
  return (
    <span className="inline-flex items-center gap-1">
      <span
        title={irregular ? '不一定有這班' : undefined}
        className={`inline-flex items-center gap-1 rounded-md border px-2 text-sm tabular-nums ${
          isNext
            ? 'border-brand bg-brand text-on-brand'
            : `bg-surface-2 text-text ${irregular ? 'border-dashed border-border-strong' : 'border-border'}`
        }`}
        style={{ minHeight: 32 }}
      >
        {formatDeparture(departure)}
        <button
          type="button"
          aria-label={`刪除 ${formatDeparture(departure)}`}
          onClick={onDelete}
          className="px-0.5 text-xs opacity-60 hover:opacity-100"
          style={{ minHeight: 0 }}
        >
          ✕
        </button>
      </span>
      {isNext && <span className="text-xs text-brand">下一班</span>}
    </span>
  )
}

function DepartureAdder({ dayType, onAdd }) {
  const [text, setText] = useState('')
  const [error, setError] = useState(null)

  const submit = async () => {
    if (text.trim() === '') return
    const parsed = parseDepartureInput(text)
    if (!parsed) {
      setError('時間格式不對')
      return
    }
    try {
      await onAdd({ day_type: dayType, ...parsed })
      setText('')
      setError(null)
    } catch (caught) {
      setError(caught instanceof ApiError && caught.status === 409 ? '這班已經有了' : '發生錯誤')
    }
  }

  return (
    <div>
      <input
        value={text}
        aria-label={`${DAY_TYPE_LABELS[dayType]}加一班`}
        placeholder="加一班，例如 *13:40"
        onChange={(event) => {
          setText(event.target.value)
          setError(null)
        }}
        onKeyDown={keysFor(submit, () => setText(''))}
        className={`${inputClass} w-44`}
      />
      {error && (
        <p role="alert" className="m-0 mt-1 text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  )
}

function DayTypeRow({ dayType, departures, next, onAdd, onDelete }) {
  const buckets = groupByBucket(departures)
  return (
    <div className="border-t border-border py-2">
      <h4 className="m-0 mb-1 text-sm font-medium">{DAY_TYPE_LABELS[dayType]}</h4>
      <div className="flex flex-wrap gap-x-4 gap-y-2">
        {BUCKETS.filter((bucket) => buckets[bucket].length > 0).map((bucket) => (
          <div key={bucket} className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-text-faint">{BUCKET_LABELS[bucket]}</span>
            {buckets[bucket].map((departure) => (
              <Chip
                key={departure.id}
                departure={departure}
                isNext={next?.id === departure.id}
                onDelete={() => onDelete(departure.id)}
              />
            ))}
          </div>
        ))}
        <DepartureAdder dayType={dayType} onAdd={onAdd} />
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <>
      <dt className="self-center text-sm text-text-muted">{label}</dt>
      <dd className="m-0 min-w-0">{children}</dd>
    </>
  )
}

/** A pair of cells shown as "起點 → 終點". */
function PairField({ label, from, to, fromLabel, toLabel, onFrom, onTo }) {
  return (
    <Field label={label}>
      <div className="flex min-w-0 items-center">
        <TextCell value={from} placeholder={fromLabel} onCommit={onFrom} />
        <span className="text-text-faint">→</span>
        <TextCell value={to} placeholder={toLabel} onCommit={onTo} />
      </div>
    </Field>
  )
}

/** A ⋯ button and the menu it opens, for the one action a card or route has. */
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

function OptionCard({ option, now, actions }) {
  const patch = (changes) => actions.patchOption(option.id, changes)
  const groups = groupByDayType(option.departures)
  const next = nextDeparture(option.departures, now)
  const [confirming, setConfirming] = useState(false)

  return (
    <article className="rounded-md border border-border bg-surface p-3">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0 flex-1 text-base font-semibold">
          <TextCell
            value={option.mode}
            placeholder="交通方式"
            onCommit={required((mode) => patch({ mode }))}
          />
        </div>
        <DeleteMenu
          label="刪除交通方式"
          menuLabel={`${option.mode} 的選單`}
          onSelect={() => setConfirming(true)}
        />
      </div>

      <dl className="m-0 mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
        <Field label="方向">
          <TextCell value={option.direction} placeholder="—" onCommit={(direction) => patch({ direction })} />
        </Field>
        <PairField
          label="起點 → 終點"
          from={option.line_from}
          to={option.line_to}
          fromLabel="起點"
          toLabel="終點"
          onFrom={(line_from) => patch({ line_from })}
          onTo={(line_to) => patch({ line_to })}
        />
        <PairField
          label="實際起點 → 實際終點"
          from={option.board_at}
          to={option.alight_at}
          fromLabel="實際起點"
          toLabel="實際終點"
          onFrom={(board_at) => patch({ board_at })}
          onTo={(alight_at) => patch({ alight_at })}
        />
        <Field label="價錢">
          <PriceCell price={option.price} onCommit={(price) => patch({ price })} />
        </Field>
        <Field label="時間">
          <TextCell value={option.duration} placeholder="—" onCommit={(duration) => patch({ duration })} />
        </Field>
        <Field label="班次間隔">
          <TextCell value={option.headway} placeholder="—" onCommit={(headway) => patch({ headway })} />
        </Field>
        <Field label="提前買票">
          <button
            type="button"
            aria-pressed={option.advance_ticket}
            onClick={() => patch({ advance_ticket: !option.advance_ticket })}
            className={`rounded-md px-3 text-sm ${
              option.advance_ticket ? 'bg-brand text-on-brand' : 'bg-surface-2 text-text-muted'
            }`}
            style={{ minHeight: 32 }}
          >
            {ADVANCE_TICKET_LABELS[option.advance_ticket]}
          </button>
        </Field>
        <Field label="備註">
          <TextCell value={option.notes} placeholder="—" onCommit={(notes) => patch({ notes })} />
        </Field>
      </dl>

      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        <LinkField label="路線圖" url={option.route_map_url} onCommit={(route_map_url) => patch({ route_map_url })} />
        <LinkField label="時刻表" url={option.timetable_url} onCommit={(timetable_url) => patch({ timetable_url })} />
        <LinkField label="即時動態" url={option.live_url} onCommit={(live_url) => patch({ live_url })} />
      </div>

      <div className="mt-3">
        {DAY_TYPES.map((dayType) => (
          <DayTypeRow
            key={dayType}
            dayType={dayType}
            departures={groups[dayType]}
            next={next}
            onAdd={(payload) => actions.addDeparture(option.id, payload)}
            onDelete={actions.deleteDeparture}
          />
        ))}
      </div>

      {confirming && (
        <ConfirmDialog
          title={`刪除「${option.mode}」？`}
          body="這個交通方式和它所有的班次都會一起刪除。"
          confirmLabel="刪除"
          onConfirm={() => {
            setConfirming(false)
            actions.deleteOption(option.id)
          }}
          onCancel={() => setConfirming(false)}
        />
      )}
    </article>
  )
}

function AddOption({ onAdd }) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState('')

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className={`${smallButton} self-start`}>
        + 新增交通方式
      </button>
    )
  }
  return (
    <input
      autoFocus
      value={mode}
      aria-label="交通方式"
      placeholder="交通方式，例如 公車 307，按 Enter 新增"
      onChange={(event) => setMode(event.target.value)}
      onBlur={() => {
        if (mode.trim() === '') setOpen(false)
      }}
      onKeyDown={keysFor(
        () => {
          if (!mode.trim()) return
          onAdd(mode.trim())
          setMode('')
          setOpen(false)
        },
        () => {
          setMode('')
          setOpen(false)
        },
      )}
      className={`${inputClass} w-full sm:w-80`}
    />
  )
}

function RouteSection({ route, now, actions }) {
  const [confirming, setConfirming] = useState(false)
  const patch = (changes) => actions.patchRoute(route.id, changes)

  return (
    <section className="mt-6">
      <div className="flex items-center justify-between gap-2">
        <h2 className="m-0 flex min-w-0 flex-1 flex-wrap items-center text-lg font-semibold">
          <span className="[&_button]:w-auto [&_input]:w-40">
            <TextCell
              value={route.from_place}
              placeholder="起點"
              onCommit={required((from_place) => patch({ from_place }))}
            />
          </span>
          <span aria-hidden="true">→</span>
          <span className="[&_button]:w-auto [&_input]:w-40">
            <TextCell
              value={route.to_place}
              placeholder="終點"
              onCommit={required((to_place) => patch({ to_place }))}
            />
          </span>
        </h2>
        <DeleteMenu
          label="刪除路線"
          menuLabel={`${route.from_place} → ${route.to_place} 的選單`}
          onSelect={() => setConfirming(true)}
        />
      </div>
      <TextCell value={route.notes} placeholder="備註" onCommit={(notes) => patch({ notes })} />

      <div className="mt-2 flex flex-col gap-3">
        {route.options.map((option) => (
          <OptionCard key={option.id} option={option} now={now} actions={actions} />
        ))}
        <AddOption onAdd={(mode) => actions.addOption(route.id, mode)} />
      </div>

      {confirming && (
        <ConfirmDialog
          title={`刪除「${route.from_place} → ${route.to_place}」？`}
          body="這條路線、它的交通方式和所有班次都會一起刪除。"
          confirmLabel="刪除"
          onConfirm={() => {
            setConfirming(false)
            actions.deleteRoute(route.id)
          }}
          onCancel={() => setConfirming(false)}
        />
      )}
    </section>
  )
}

function AddRoute({ onAdd }) {
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const ready = from.trim() !== '' && to.trim() !== ''

  const submit = () => {
    if (!ready) return
    onAdd(from.trim(), to.trim())
    setFrom('')
    setTo('')
  }
  const onKeyDown = keysFor(submit, () => {})

  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        value={from}
        aria-label="起點"
        placeholder="起點"
        onChange={(event) => setFrom(event.target.value)}
        onKeyDown={onKeyDown}
        className={`${inputClass} w-36`}
      />
      <span className="text-text-faint">→</span>
      <input
        value={to}
        aria-label="終點"
        placeholder="終點"
        onChange={(event) => setTo(event.target.value)}
        onKeyDown={onKeyDown}
        className={`${inputClass} w-36`}
      />
      <button type="button" onClick={submit} disabled={!ready} className={smallButton}>
        + 新增路線
      </button>
    </div>
  )
}

export default function Transport() {
  const routes = useApiQuery(KEY, endpoints.transport.routes())
  const now = useNow()

  const patchRoute = useTransportMutation(({ id, changes }) =>
    send(endpoints.transport.route(id), 'PATCH', changes),
  )
  const deleteRoute = useTransportMutation((id) => send(endpoints.transport.route(id), 'DELETE'))
  const addRoute = useTransportMutation((payload) =>
    send(endpoints.transport.routes(), 'POST', payload),
  )
  const addOption = useTransportMutation(({ routeId, mode }) =>
    send(endpoints.transport.options(routeId), 'POST', { mode }),
  )
  const patchOption = useTransportMutation(({ id, changes }) =>
    send(endpoints.transport.option(id), 'PATCH', changes),
  )
  const deleteOption = useTransportMutation((id) => send(endpoints.transport.option(id), 'DELETE'))
  const addDeparture = useTransportMutation(({ optionId, payload }) =>
    send(endpoints.transport.departures(optionId), 'POST', payload),
  )
  const deleteDeparture = useTransportMutation((id) =>
    send(endpoints.transport.departure(id), 'DELETE'),
  )

  if (routes.isLoading) return <LoadingState label="載入路線中…" />
  if (routes.isError) return <ErrorState error={routes.error} onRetry={routes.refetch} />

  const actions = {
    patchRoute: (id, changes) => patchRoute.mutate({ id, changes }),
    deleteRoute: (id) => deleteRoute.mutate(id),
    addOption: (routeId, mode) => addOption.mutate({ routeId, mode }),
    patchOption: (id, changes) => patchOption.mutate({ id, changes }),
    deleteOption: (id) => deleteOption.mutate(id),
    // Returns the promise: the adder shows a 409 under its own input.
    addDeparture: (optionId, payload) => addDeparture.mutateAsync({ optionId, payload }),
    deleteDeparture: (id) => deleteDeparture.mutate(id),
  }
  const createRoute = (from_place, to_place) => addRoute.mutate({ from_place, to_place })

  return (
    <main className="mx-auto max-w-4xl overflow-x-hidden px-4 pb-16 pt-6">
      <h1 className="m-0 text-xl font-semibold">Transportation</h1>

      {routes.data.length === 0 ? (
        <EmptyState
          action={
            <div className="flex justify-center">
              <AddRoute onAdd={createRoute} />
            </div>
          }
        >
          還沒有路線。
        </EmptyState>
      ) : (
        <>
          {routes.data.map((route) => (
            <RouteSection key={route.id} route={route} now={now} actions={actions} />
          ))}
          <div className="mt-8 border-t border-border pt-4">
            <AddRoute onAdd={createRoute} />
          </div>
        </>
      )}
    </main>
  )
}
