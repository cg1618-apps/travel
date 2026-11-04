/**
 * 行程: one trip, in full, entry by entry (一段 on screen, a leg in the API).
 *
 * The sheet's tab, as cards — one per entry, with the booking code large
 * enough to read off a phone at a ticket gate. `/trips/:tripId` only - the
 * index is `Trips.jsx`. A trip carries 狀態, 保存, 當作範本, 已準備完成, its
 * ticket status and 單程 / 來回 in its header; ← 行程 returns to the tab it is
 * on, and the whole header sticks to the top while the entries scroll under
 * it. Every field is a cell that commits on Enter or blur; the times, the
 * packing list link and the ticks are the exceptions, because each has a
 * refusal worth showing.
 *
 * What a card shows follows its 類型 (`lib/legTypes.js`): the type's fields,
 * and the ticks and booking code it has - fixed ones always, optional ones
 * when switched on in the card's ⋯ menu.
 *
 * A round trip (來回) shows two sections, 去程 and 回程, each with its own
 * title, remark and + 新增一段; an entry moves between them from its ⋯ menu.
 */

import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '../api/client'
import { endpoints } from '../api/endpoints'
import { SelectCell, TextAreaCell, TextCell } from '../components/Cell'
import { Combobox } from '../components/Combobox'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { EvictDialog } from '../components/EvictDialog'
import { KindControls } from '../components/KindControls'
import { PriceCell } from '../components/PriceCell'
import { RowMenu } from '../components/RowMenu'
import { Segmented } from '../components/Segmented'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { send, useApiMutation, useApiQuery } from '../hooks/useApiQuery'
import { required } from '../lib/cells'
import { keysFor } from '../lib/keys'
import {
  AUTO_SAVE_LIMIT,
  badgeFor,
  isAutoSaved,
  linkChoices,
  linkLabel,
  tabFor,
} from '../lib/kinds'
import {
  DONE_LABEL,
  LEG_LABELS,
  RIDE_TYPE_LABELS,
  ROUND_TRIP_LABELS,
  TICKET_STATUSES,
  TICKET_STATUS_LABELS,
  TRANSPORT_TYPES,
  TRANSPORT_TYPE_LABELS,
} from '../lib/labels'
import {
  RIDE_TYPES,
  TICKS,
  defaultFlags,
  fieldLabel,
  fieldsFor,
  flagField,
  flagLabel,
  shows,
  toggleableFlags,
} from '../lib/legTypes'
import { parseWholeNumber } from '../lib/numbers'
import {
  fillArrival,
  firstDeparture,
  formatLegTimes,
  fromTaipeiInput,
  readinessHint,
  sortLegs,
  taipeiInputValue,
  tripReadiness,
  unlinkedNotice,
} from '../lib/trips'

const TRIPS = ['trips']
const INVALIDATE = [TRIPS, ['packing-list'], ['packing-lists'], ['label-options']]
const COPIED_MS = 2000
const SECTIONS = ['outbound', 'return']
// Where each section keeps its title and remark. The 去程 remark is the
// trip's own `notes`, so nothing moves when a trip turns round.
const SECTION_FIELDS = {
  outbound: { title: 'outbound_title', remark: 'notes' },
  return: { title: 'return_title', remark: 'return_notes' },
}

const inputClass = 'rounded-md border border-border bg-canvas px-2 py-1.5 text-sm text-text min-w-0'
const smallButton = 'rounded-md border border-border-strong px-3 text-sm text-text-muted'
const editButton = 'px-1 text-xs text-text-faint hover:text-text'

const hasStatus = (error, status) => error instanceof ApiError && error.status === status
// An id that is not a number - /trips/current, a stale /trips/<word> - is a
// 422 from the API rather than a 404, and means the same: no such trip.
const notFound = (error) => hasStatus(error, 404) || hasStatus(error, 422)

function useTripMutation(mutationFn, onError) {
  return useApiMutation({ invalidate: INVALIDATE, mutationFn, onError })
}

function Field({ label, children }) {
  return (
    <>
      <dt className="self-center text-sm text-text-muted">{label}</dt>
      <dd className="m-0 min-w-0">{children}</dd>
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

/**
 * The trip header's ⋯: 保存 (or 取消保存), 當作範本, 刪除行程. A 範本's kind
 * never changes, so it offers only 刪除行程.
 */
function TripMenu({ trip, onToggleSaved, onMakeTemplate, onDelete }) {
  const [open, setOpen] = useState(false)
  const remove = { label: '刪除行程', danger: true, onSelect: onDelete }
  const actions =
    trip.kind === 'template'
      ? [remove]
      : [
          { label: trip.kind === 'saved' ? '取消保存' : '保存', onSelect: onToggleSaved },
          { label: '當作範本', onSelect: onMakeTemplate },
          remove,
        ]
  return (
    <>
      <button
        type="button"
        aria-label={`${trip.name} 的選單`}
        aria-haspopup="menu"
        onClick={() => setOpen(true)}
        className="px-2 text-text-faint hover:text-text"
        style={{ minHeight: 0 }}
      >
        ⋯
      </button>
      <RowMenu open={open} onClose={() => setOpen(false)} actions={actions} />
    </>
  )
}

/** After a copy: which template legs had a packing list the copy did not carry. */
function UnlinkedNotice({ entries, onDismiss }) {
  if (!entries?.length) return null
  return (
    <div
      role="status"
      className="mt-3 rounded-md border border-border-strong bg-surface-2 p-3 text-sm"
    >
      {entries.map((entry) => (
        <p key={`${entry.from_place}-${entry.to_place}-${entry.packing_list_name}`} className="m-0">
          {unlinkedNotice(entry)}
        </p>
      ))}
      <button type="button" onClick={onDismiss} className={`${smallButton} mt-2`}>
        知道了
      </button>
    </div>
  )
}

/**
 * 訂票代碼 (訂單編號 on 開車 and 腳踏車): tap to copy, ✎ to edit. The clipboard
 * can refuse, so that is handled.
 */
function BookingCode({ code, label, onCommit }) {
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
        aria-label={label}
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
        <span className="flex-1 text-sm text-text-faint">沒有{label}</span>
      )}
      <button
        type="button"
        aria-label={`編輯${label}`}
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

/**
 * 出發 and 抵達, read and written in Taipei time. Both optional; choosing a
 * departure while the arrival is empty fills the arrival with it, as the
 * server would on save.
 */
function TimesInputs({ departs, arrives, onDeparts, onArrives }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        type="datetime-local"
        aria-label="出發時間"
        value={departs}
        onChange={(event) => {
          onDeparts(event.target.value)
          onArrives(fillArrival(event.target.value, arrives))
        }}
        className={inputClass}
      />
      <span className="text-text-faint">→</span>
      <input
        type="datetime-local"
        aria-label="抵達時間"
        value={arrives}
        onChange={(event) => onArrives(event.target.value)}
        className={inputClass}
      />
    </div>
  )
}

const timeValue = (iso) => (iso ? taipeiInputValue(iso) : '')
const timePayload = (value) => (value ? fromTaipeiInput(value) : null)
const TIMES_REFUSED = '抵達時間不能早於出發時間'

function TimesEditor({ leg, onSave, onCancel, problem }) {
  const [departs, setDeparts] = useState(timeValue(leg.departs_at))
  const [arrives, setArrives] = useState(timeValue(leg.arrives_at))

  return (
    <div className="mt-1">
      <div className="flex flex-wrap items-center gap-2">
        <TimesInputs departs={departs} arrives={arrives} onDeparts={setDeparts} onArrives={setArrives} />
        <button
          type="button"
          onClick={() =>
            onSave({ departs_at: timePayload(departs), arrives_at: timePayload(arrives) })
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

  const choices = lists.data ? linkChoices(lists.data, leg.packing_list_id) : []

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
              {linkLabel(list)}
            </option>
          ))}
        </select>
      )}
      <Problem>{problem}</Problem>
    </div>
  )
}

/** '' stands for no ride type, as SelectCell's convention has it. */
const rideTypeOptions = (type) => ['', ...(RIDE_TYPES[type] ?? [])]
const RIDE_TYPE_OPTION_LABELS = { '': '—', ...RIDE_TYPE_LABELS }

/** One of the type's fields on a card, as the cell that field needs. */
function LegFieldCell({ leg, field, ticketTypes, patch }) {
  const value = leg[field] ?? null
  const commit = (next) => patch({ [field]: next })
  if (field === 'price') return <PriceCell price={value} onCommit={commit} />
  if (field === 'ride_type') {
    return (
      <SelectCell
        value={value}
        options={rideTypeOptions(leg.transport_type)}
        labels={RIDE_TYPE_OPTION_LABELS}
        ariaLabel={fieldLabel(leg.transport_type, field)}
        onCommit={commit}
      />
    )
  }
  return (
    <TextCell
      value={value}
      placeholder="—"
      options={field === 'ticket_type' ? ticketTypes : []}
      onCommit={commit}
    />
  )
}

/**
 * An entry's ⋯: 移到去程 / 移到回程 on a round trip, 顯示 / 隱藏 for each of
 * the type's optional ticks and code, and 刪除這段.
 */
function LegMenu({ leg, roundTrip, onPatch, onDelete }) {
  const [open, setOpen] = useState(false)
  const type = leg.transport_type
  const actions = []
  if (roundTrip) {
    const target = leg.section === 'return' ? 'outbound' : 'return'
    actions.push({ label: `移到${LEG_LABELS[target]}`, onSelect: () => onPatch({ section: target }) })
  }
  for (const flag of toggleableFlags(type)) {
    const on = Boolean(leg[flagField(flag)])
    actions.push({
      label: `${on ? '隱藏' : '顯示'}「${flagLabel(type, flag)}」`,
      onSelect: () => onPatch({ [flagField(flag)]: !on }),
    })
  }
  actions.push({ label: '刪除這段', danger: true, onSelect: onDelete })
  return (
    <>
      <button
        type="button"
        aria-label={`${leg.from_place} → ${leg.to_place} 的選單`}
        aria-haspopup="menu"
        onClick={() => setOpen(true)}
        className="px-2 text-text-faint hover:text-text"
        style={{ minHeight: 0 }}
      >
        ⋯
      </button>
      <RowMenu open={open} onClose={() => setOpen(false)} actions={actions} />
    </>
  )
}

/** The 類型 select, used on a card and first in the add form. */
function TypeSelect({ value, onChange, placeholder, autoFocus = false, className = '' }) {
  return (
    <select
      autoFocus={autoFocus}
      aria-label="類型"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className={`${inputClass} ${className}`}
    >
      {placeholder && (
        <option value="" disabled>
          {placeholder}
        </option>
      )}
      {TRANSPORT_TYPES.map((type) => (
        <option key={type} value={type}>
          {TRANSPORT_TYPE_LABELS[type]}
        </option>
      ))}
    </select>
  )
}

function LegCard({ leg, roundTrip, ticketTypes, actions }) {
  const [editingTimes, setEditingTimes] = useState(false)
  const [timesProblem, setTimesProblem] = useState(null)
  const [confirming, setConfirming] = useState(false)
  const type = leg.transport_type
  const patch = (changes) => actions.patchLeg.mutate({ id: leg.id, changes })
  const patchAsync = (changes) => actions.patchLeg.mutateAsync({ id: leg.id, changes })
  const fields = fieldsFor(type)
  const ticks = TICKS.filter((tick) => shows(leg, tick))
  const times = formatLegTimes(leg)

  const saveTimes = async (changes) => {
    try {
      await patchAsync(changes)
      setTimesProblem(null)
      setEditingTimes(false)
    } catch (caught) {
      setTimesProblem(hasStatus(caught, 422) ? TIMES_REFUSED : '發生錯誤')
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
            {times ? <span>{times}</span> : <span className="text-text-faint">未定時間</span>}
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
        <TypeSelect
          value={type}
          onChange={(transport_type) => patch({ transport_type })}
          className="shrink-0 py-1"
        />
        <LegMenu
          leg={leg}
          roundTrip={roundTrip}
          onPatch={patch}
          onDelete={() => setConfirming(true)}
        />
      </div>

      {fields.length > 0 && (
        <dl className="m-0 mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
          {fields.map((field) => (
            <Field key={field} label={fieldLabel(type, field)}>
              <LegFieldCell leg={leg} field={field} ticketTypes={ticketTypes} patch={patch} />
            </Field>
          ))}
        </dl>
      )}

      {shows(leg, 'booking_code') && (
        <div className="mt-2">
          <BookingCode
            code={leg.booking_code}
            label={flagLabel(type, 'booking_code')}
            onCommit={(booking_code) => patch({ booking_code })}
          />
        </div>
      )}

      {ticks.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {ticks.map((tick) => (
            <button
              key={tick}
              type="button"
              aria-pressed={leg[tick]}
              onClick={() => patch({ [tick]: !leg[tick] })}
              className={`rounded-md px-3 text-sm ${
                leg[tick] ? 'bg-brand text-on-brand' : 'bg-surface-2 text-text-muted'
              }`}
              style={{ minHeight: 32 }}
            >
              {leg[tick] ? '✓ ' : ''}
              {flagLabel(type, tick)}
            </button>
          ))}
        </div>
      )}

      <dl className="m-0 mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
        <Field label="備註">
          <TextAreaCell value={leg.notes} placeholder="—" ariaLabel="備註" onCommit={(notes) => patch({ notes })} />
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

/** One field of the type in the add form: an input (車票類型 suggesting), or a ride type. */
function AddField({ type, field, value, ticketTypes, onChange }) {
  const label = fieldLabel(type, field)
  if (field === 'ride_type') {
    return (
      <select
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={inputClass}
      >
        {rideTypeOptions(type).map((option) => (
          <option key={option} value={option}>
            {option === '' ? label : RIDE_TYPE_LABELS[option]}
          </option>
        ))}
      </select>
    )
  }
  if (field === 'ticket_type') {
    return (
      <Combobox
        aria-label={label}
        placeholder={label}
        value={value}
        onChange={onChange}
        options={ticketTypes}
        className={`${inputClass} w-28`}
      />
    )
  }
  return (
    <input
      aria-label={label}
      placeholder={label}
      inputMode={field === 'price' ? 'numeric' : undefined}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className={`${inputClass} w-28`}
    />
  )
}

/**
 * + 新增一段: 類型 first, then only that type's fields, and a 顯示 checkbox
 * for each optional tick and code, starting at the type's default. Times are
 * optional. The booking code and 備註 are filled in on the card.
 */
function AddLeg({ ticketTypes, onAdd }) {
  const [open, setOpen] = useState(false)
  const [type, setType] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [departs, setDeparts] = useState('')
  const [arrives, setArrives] = useState('')
  const [values, setValues] = useState({})
  const [flags, setFlags] = useState({})
  const [problem, setProblem] = useState(null)
  const ready = type && from.trim() && to.trim()

  const reset = () => {
    setType('')
    setFrom('')
    setTo('')
    setDeparts('')
    setArrives('')
    setValues({})
    setFlags({})
    setProblem(null)
    setOpen(false)
  }

  const pickType = (next) => {
    setType(next)
    setFlags(defaultFlags(next))
  }

  const submit = async () => {
    if (!ready) return
    const payload = {
      transport_type: type,
      from_place: from.trim(),
      to_place: to.trim(),
      departs_at: timePayload(departs),
      arrives_at: timePayload(arrives),
    }
    for (const field of fieldsFor(type)) {
      const text = (values[field] ?? '').trim()
      if (field === 'price') {
        const price = parseWholeNumber(text)
        if (price === undefined) {
          setProblem('價錢要是整數')
          return
        }
        payload.price = price
      } else {
        payload[field] = text || null
      }
    }
    for (const flag of toggleableFlags(type)) payload[flagField(flag)] = Boolean(flags[flagField(flag)])
    try {
      await onAdd(payload)
      reset()
    } catch (caught) {
      setProblem(hasStatus(caught, 422) ? TIMES_REFUSED : '發生錯誤')
    }
  }

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className={`${smallButton} self-start`}>
        + 新增一段
      </button>
    )
  }
  const optional = type ? toggleableFlags(type) : []
  return (
    <div className="rounded-md border border-dashed border-border-strong p-3">
      <TypeSelect value={type} onChange={pickType} placeholder="選擇類型" autoFocus />
      {type && (
        <>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <input
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
          <div className="mt-2">
            <TimesInputs departs={departs} arrives={arrives} onDeparts={setDeparts} onArrives={setArrives} />
          </div>
          {fieldsFor(type).length > 0 && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {fieldsFor(type).map((field) => (
                <AddField
                  key={field}
                  type={type}
                  field={field}
                  value={values[field] ?? ''}
                  ticketTypes={ticketTypes}
                  onChange={(value) => setValues({ ...values, [field]: value })}
                />
              ))}
            </div>
          )}
          {optional.length > 0 && (
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-text-muted">
              <span>顯示</span>
              {optional.map((flag) => (
                <label key={flag} className="flex items-center gap-1">
                  <input
                    type="checkbox"
                    className="size-4"
                    checked={Boolean(flags[flagField(flag)])}
                    onChange={(event) => setFlags({ ...flags, [flagField(flag)]: event.target.checked })}
                  />
                  {flagLabel(type, flag)}
                </label>
              ))}
            </div>
          )}
        </>
      )}
      <div className="mt-2 flex gap-2">
        <button type="button" disabled={!ready} onClick={submit} className={`${smallButton} disabled:opacity-40`}>
          新增
        </button>
        <button type="button" onClick={reset} className={smallButton}>
          取消
        </button>
      </div>
      <Problem>{problem}</Problem>
    </div>
  )
}

const badge = 'shrink-0 rounded-sm bg-surface-2 px-2 text-xs font-normal text-text-muted'

/**
 * 已準備完成 and the ticket status, side by side. The checkbox cannot be
 * ticked until the trip is ready - the hint says what is missing - but can
 * always be unticked. The server decides the same, so a 422 is still shown.
 */
function Readiness({ trip, onPatch }) {
  const [problem, setProblem] = useState(null)
  const readiness = tripReadiness(trip)
  const hint = readinessHint(readiness)
  const blocked = !trip.done && !readiness.ready

  const setDone = async (done) => {
    try {
      await onPatch({ done })
      setProblem(null)
    } catch (caught) {
      setProblem(hasStatus(caught, 422) ? `還沒準備完成：${hint ?? caught.message}` : '發生錯誤')
    }
  }

  return (
    <>
      <label className={`flex items-center gap-1 text-sm ${blocked ? 'text-text-faint' : 'text-text-muted'}`}>
        <input
          type="checkbox"
          checked={Boolean(trip.done)}
          disabled={blocked}
          onChange={(event) => setDone(event.target.checked)}
          aria-label={`「${trip.name}」${DONE_LABEL}`}
          aria-describedby={blocked ? 'readiness-hint' : undefined}
          className="size-4"
        />
        {DONE_LABEL}
        {blocked && (
          <span id="readiness-hint" className="text-xs">
            （{hint}）
          </span>
        )}
      </label>
      <Segmented
        value={trip.ticket_status}
        options={TICKET_STATUSES}
        labels={TICKET_STATUS_LABELS}
        ariaLabel="買票狀態"
        onChange={(ticket_status) => onPatch({ ticket_status }).catch(() => setProblem('發生錯誤'))}
      />
      {problem && (
        <p role="alert" className="m-0 w-full text-xs text-danger">
          {problem}
        </p>
      )}
    </>
  )
}

/** 單程 / 來回. Back to 單程 is refused while 回程 still holds anything. */
function RoundTripToggle({ trip, onPatch }) {
  const [problem, setProblem] = useState(null)
  const change = async (round_trip) => {
    try {
      await onPatch({ round_trip })
      setProblem(null)
    } catch (caught) {
      setProblem(
        hasStatus(caught, 422)
          ? '回程還有行程段、標題或備註。請先移到去程或刪除，再改回單程。'
          : '發生錯誤',
      )
    }
  }
  return (
    <>
      <Segmented
        value={Boolean(trip.round_trip)}
        options={[false, true]}
        labels={ROUND_TRIP_LABELS}
        ariaLabel="單程或來回"
        onChange={change}
      />
      {problem && (
        <p role="alert" className="m-0 w-full text-xs text-danger">
          {problem}
        </p>
      )}
    </>
  )
}

/** The entries of one section (or of a one-way trip), then + 新增一段. */
function LegList({ legs, trip, section, ticketTypes, actions, empty }) {
  return (
    <div className="mt-2 flex flex-col gap-3">
      {legs.length === 0 && <EmptyState>{empty}</EmptyState>}
      {legs.map((leg) => (
        <LegCard
          key={leg.id}
          leg={leg}
          roundTrip={Boolean(trip.round_trip)}
          ticketTypes={ticketTypes}
          actions={actions}
        />
      ))}
      <AddLeg
        ticketTypes={ticketTypes}
        onAdd={(payload) =>
          actions.addLeg.mutateAsync({
            tripId: trip.id,
            payload: section ? { ...payload, section } : payload,
          })
        }
      />
    </div>
  )
}

/** 去程 or 回程 on a round trip: its title, its remark, its entries. */
function Section({ section, trip, legs, ticketTypes, actions, onPatchTrip }) {
  const label = LEG_LABELS[section]
  const { title, remark } = SECTION_FIELDS[section]
  return (
    <section className="mt-6" aria-label={label}>
      <div className="flex items-center gap-2 border-b border-border pb-1">
        <h2 className="m-0 shrink-0 text-sm font-semibold text-text-muted">{label}</h2>
        <div className="min-w-0 flex-1 font-semibold">
          <TextCell
            value={trip[title]}
            placeholder={`${label}標題`}
            onCommit={(value) => onPatchTrip({ [title]: value })}
          />
        </div>
      </div>
      <TextAreaCell
        value={trip[remark]}
        placeholder={`${label}備註`}
        ariaLabel={`${label}備註`}
        onCommit={(value) => onPatchTrip({ [remark]: value })}
      />
      <LegList
        legs={legs}
        trip={trip}
        section={section}
        ticketTypes={ticketTypes}
        actions={actions}
        empty={`${label}還沒有任何一段。`}
      />
    </section>
  )
}

function TripView({ trip, unlinked, ticketTypes, actions, onDeleted, onDismissNotice }) {
  const [confirming, setConfirming] = useState(false)
  const [confirmingUnsave, setConfirmingUnsave] = useState(false)
  const legs = sortLegs(trip.legs)
  const patchTrip = (changes) => actions.patchTrip.mutate({ id: trip.id, changes })
  const patchTripAsync = (changes) => actions.patchTrip.mutateAsync({ id: trip.id, changes })
  const makeTemplate = () => actions.makeTemplate(trip)
  const tab = tabFor(trip)
  const roundTrip = Boolean(trip.round_trip)
  // An entry with no section on a round trip is shown under 去程, which is
  // where the server puts it.
  const sectionOf = (leg) => (leg.section === 'return' ? 'return' : 'outbound')

  return (
    <>
      {/* The header sticks, so the trip's name, 狀態 and 備註 stay in view over
          a long run of legs. -mx-4 px-4 carries the canvas to the column's
          edges past the shell's padding; -mt-3 pt-3 keeps the unscrolled
          layout where it was while leaving a little air once it is stuck. z-10
          lifts it over the leg cards, which set no z-index of their own, and
          stays under the z-50 dialogs and menus. */}
      <div className="sticky top-0 z-10 -mx-4 -mt-3 border-b border-border bg-canvas px-4 pt-3 pb-3">
        <Link
          to={tab === 'free' ? '/trips' : `/trips?tab=${tab}`}
          className="text-sm text-text-faint no-underline"
        >
          ← 行程
        </Link>
        <div className="mt-2 flex items-center justify-between gap-2">
          <h1 className="m-0 flex min-w-0 flex-1 items-center gap-2 text-xl font-semibold">
            <span className="min-w-0 flex-1">
              <TextCell
                value={trip.name}
                placeholder="行程名稱"
                onCommit={required((name) => patchTrip({ name }))}
              />
            </span>
            {badgeFor(trip) && <span className={badge}>{badgeFor(trip)}</span>}
          </h1>
          <TripMenu
            trip={trip}
            onToggleSaved={() =>
              trip.kind === 'saved' ? setConfirmingUnsave(true) : patchTrip({ kind: 'saved' })
            }
            onMakeTemplate={makeTemplate}
            onDelete={() => setConfirming(true)}
          />
        </div>
        {/* 已準備完成 and the tickets are this trip's own, independent of 狀態
            and kind; a 範本 is only a starting point, so it has neither. */}
        <div className="flex flex-wrap items-center gap-2">
          <KindControls row={trip} noun="行程" onPatch={patchTrip} onMakeTemplate={makeTemplate} />
          {trip.kind !== 'template' && <Readiness trip={trip} onPatch={patchTripAsync} />}
          <RoundTripToggle trip={trip} onPatch={patchTripAsync} />
        </div>
        {!roundTrip && (
          <TextAreaCell
            value={trip.notes}
            placeholder="備註"
            ariaLabel="備註"
            onCommit={(notes) => patchTrip({ notes })}
          />
        )}
        {(trip.kind === 'saved' || isAutoSaved(trip) || trip.archive_note) && (
          <TextAreaCell
            value={trip.archive_note}
            placeholder="保存備註"
            ariaLabel="保存備註"
            onCommit={(archive_note) => patchTrip({ archive_note })}
          />
        )}
      </div>
      <UnlinkedNotice entries={unlinked} onDismiss={onDismissNotice} />

      {roundTrip ? (
        SECTIONS.map((section) => (
          <Section
            key={section}
            section={section}
            trip={trip}
            legs={legs.filter((leg) => sectionOf(leg) === section)}
            ticketTypes={ticketTypes}
            actions={actions}
            onPatchTrip={patchTrip}
          />
        ))
      ) : (
        <div className="mt-2">
          <LegList
            legs={legs}
            trip={trip}
            ticketTypes={ticketTypes}
            actions={actions}
            empty="這個行程還沒有任何一段。"
          />
        </div>
      )}

      {confirmingUnsave && (
        <ConfirmDialog
          title={`取消保存「${trip.name}」？`}
          body="取消保存後會回到一般行程（未使用）。"
          confirmLabel="取消保存"
          onConfirm={() => {
            setConfirmingUnsave(false)
            patchTrip({ kind: 'free' })
          }}
          onCancel={() => setConfirmingUnsave(false)}
        />
      )}
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
  const location = useLocation()
  // A refused 過去使用's changes: a decision to put to the person.
  const [refusal, setRefusal] = useState(null)

  const trip = useApiQuery(
    [...TRIPS, 'detail', tripId],
    endpoints.trips.detail(tripId),
    // A 404 or 422 is an answer (no such trip), not a failure worth retrying.
    { retry: (count, error) => !notFound(error) && count < 1 },
  )
  const options = useApiQuery(['label-options'], endpoints.labelOptions.index())
  // Only while a 409 is waiting on a decision: the index names what would go.
  const index = useApiQuery([...TRIPS, 'index'], endpoints.trips.index(), {
    enabled: Boolean(refusal),
  })

  const createTrip = useTripMutation((payload) => send(endpoints.trips.index(), 'POST', payload))
  const patchTrip = useTripMutation(
    ({ id, changes }) => send(endpoints.trips.detail(id), 'PATCH', changes),
    // A 409 is a decision to put to the person, not a failure to report.
    (error, variables) => {
      if (hasStatus(error, 409)) setRefusal(variables.changes)
    },
  )
  const deleteTrip = useTripMutation((id) => send(endpoints.trips.detail(id), 'DELETE'))
  const addLeg = useTripMutation(({ tripId: id, payload }) =>
    send(endpoints.trips.legs(id), 'POST', payload),
  )
  const patchLeg = useTripMutation(({ id, changes }) =>
    send(endpoints.trips.leg(id), 'PATCH', changes),
  )
  const deleteLeg = useTripMutation((id) => send(endpoints.trips.leg(id), 'DELETE'))

  const makeTemplate = (source) => {
    // 當作範本 keeps the dates: the copy starts on the source's own first day.
    // A trip with no departure anywhere has nothing to move.
    const first = firstDeparture(source.legs)
    createTrip.mutate(
      {
        name: source.name,
        kind: 'template',
        copy_from_id: source.id,
        ...(first ? { start_date: taipeiInputValue(first).slice(0, 10) } : {}),
      },
      {
        onSuccess: (created) =>
          navigate(`/trips/${created.id}`, { state: { unlinked: created.unlinked_from } }),
      },
    )
  }

  if (trip.isLoading) return <LoadingState label="載入行程中…" />

  // `overflow-x-clip`, not `-hidden`: both keep a wide leg card (a long
  // booking code, two datetime inputs side by side) from scrolling the page
  // sideways on a phone, but `hidden` also makes <main> a scroll container,
  // and the sticky header would then stick to <main> instead of the viewport.
  const shell = (children) => (
    <main className="mx-auto max-w-4xl overflow-x-clip px-4 pb-16 pt-6">{children}</main>
  )

  if (trip.isError && !notFound(trip.error)) {
    return <ErrorState error={trip.error} onRetry={trip.refetch} />
  }
  if (trip.isError) {
    return shell(
      <>
        <Link to="/trips" className="text-sm text-text-faint no-underline">
          ← 行程
        </Link>
        <EmptyState>找不到這個行程。</EmptyState>
      </>,
    )
  }

  const ticketTypes = (options.data || [])
    .filter((row) => row.kind === 'ticket_type')
    .map((row) => row.value)
  const actions = { patchTrip, deleteTrip, addLeg, patchLeg, deleteLeg, makeTemplate }
  const evicting = index.data?.evict_next ?? []

  // 保存 instead moves the doomed trips to 保存, then retries the change. A
  // rejection leaves the dialog closed; the refetch shows the actual state.
  const saveInstead = async () => {
    const changes = refusal
    try {
      await Promise.all(
        evicting.map((row) =>
          patchTrip.mutateAsync({ id: row.id, changes: { kind: 'saved' } }),
        ),
      )
      setRefusal(null)
      patchTrip.mutate({ id: trip.data.id, changes })
    } catch {
      setRefusal(null)
    }
  }

  return shell(
    <>
      <TripView
        key={trip.data.id}
        trip={trip.data}
        unlinked={location.state?.unlinked}
        ticketTypes={ticketTypes}
        actions={actions}
        onDeleted={() => navigate('/trips')}
        // Cleared rather than hidden, so Back and a reload do not bring it back.
        onDismissNotice={() => navigate(location.pathname, { replace: true, state: null })}
      />
      {refusal && index.isSuccess && !index.isFetching && (
        <EvictDialog
          noun="一個行程"
          body={`自動保存最多 ${AUTO_SAVE_LIMIT.trips} 個行程。設為過去使用會刪除最舊的：`}
          evicting={evicting}
          onSaveInstead={saveInstead}
          onConfirm={() => {
            const changes = refusal
            setRefusal(null)
            patchTrip.mutate({ id: trip.data.id, changes: { ...changes, evict_confirmed: true } })
          }}
          onCancel={() => setRefusal(null)}
        />
      )}
    </>,
  )
}
