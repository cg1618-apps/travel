/**
 * The sheet's new rows: any number of them, every column filled where it
 * sits, saved together with one 儲存.
 *
 * Nothing reaches the server until then, so a row is complete when it lands
 * in its 類別 — rather than jumping into its group the moment its category
 * is typed, and having to be found again to fill in the rest. A row left
 * untouched is skipped; a row with no 項目 stops the save and says so.
 * Ctrl+Enter (⌘+Enter) anywhere in the rows saves.
 */

import { useState } from 'react'

import { draftProblems, emptyDraft, isBlank, toPayload } from '../lib/drafts'
import { CHECK_LABELS, CHECK_STATES, NEED_LABELS, NEEDS, STATUS_LABELS, TIMING_LABELS } from '../lib/labels'
import { TIMINGS } from '../lib/timing'
import { CHECK_TONES, NEED_TONES, STATUS_TONES, TIMING_TONES, toneClass, toneForText } from '../lib/tones'
import { Combobox } from './Combobox'
import { NUMBER_CELL } from './GridRow'

const STATUSES = ['not_packed', 'packed', 'no_need']
const NEED_OPTIONS = ['', ...NEEDS]
const NEED_OPTION_LABELS = { '': '—', ...NEED_LABELS }

const field =
  'w-full min-w-0 rounded-sm border border-border bg-canvas px-1.5 py-1 text-sm outline-none focus:border-brand'
const bad = 'border-danger'

// The tint of the new rows over the canvas, solid, because the pinned number
// cell has to hide what scrolls beneath it.
const NUMBER_TINT = {
  background: 'linear-gradient(var(--c-brand-soft), var(--c-brand-soft)) var(--c-canvas)',
}

function Choice({ value, options, labels, tone, label, onChange }) {
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      aria-label={label}
      className={`${field} cursor-pointer ${toneClass(tone)}`}
    >
      {options.map((option) => (
        <option key={option} value={option}>
          {labels[option]}
        </option>
      ))}
    </select>
  )
}

function DraftRow({ draft, index, number, showProblems, categories, locations, onChange, onRemove }) {
  const set = (key) => (value) => onChange({ ...draft, [key]: value })
  const text = (key) => ({
    value: draft[key],
    onChange: (event) => set(key)(event.target.value),
  })
  const problems = showProblems ? draftProblems(draft) : []
  const n = index + 1

  return (
    <tr className="border-t border-border/40 align-top">
      <td className={`${NUMBER_CELL} py-1`} style={NUMBER_TINT}>
        {number}
      </td>
      <td />
      <td className="px-1 py-1">
        <Combobox
          value={draft.category}
          onChange={set('category')}
          options={categories}
          aria-label={`新的第 ${n} 列：類別`}
          placeholder="類別"
          // The first field of a new row: where typing starts.
          autoFocus={draft.autoFocus}
          className={field}
        />
      </td>
      <td className="px-1 py-1">
        <input
          {...text('name')}
          aria-label={`新的第 ${n} 列：項目`}
          aria-invalid={problems.includes('name')}
          placeholder="項目"
          className={`${field} ${problems.includes('name') ? bad : ''}`}
        />
      </td>
      <td className="px-1 py-1">
        <input {...text('detail')} aria-label={`新的第 ${n} 列：細項`} placeholder="細項" className={`${field} min-w-20`} />
      </td>
      <td className="px-1 py-1">
        {/* One box, as 數量 is one cell: "5 雙" is one fact. Its own min width,
            or the table squeezes the two inputs to slivers. */}
        <div
          className={`flex min-w-24 items-center rounded-sm border bg-canvas text-sm focus-within:border-brand ${
            problems.includes('quantity') ? bad : 'border-border'
          }`}
        >
          <input
            {...text('quantity')}
            inputMode="numeric"
            aria-label={`新的第 ${n} 列：數量`}
            aria-invalid={problems.includes('quantity')}
            placeholder="數量"
            className="w-10 min-w-0 bg-transparent px-1.5 py-1 text-right tabular-nums outline-none"
          />
          <span aria-hidden="true" className="h-4 border-l border-border" />
          <input
            {...text('unit')}
            aria-label={`新的第 ${n} 列：單位`}
            placeholder="單位"
            className="w-12 min-w-0 bg-transparent px-1.5 py-1 outline-none"
          />
        </div>
      </td>
      <td className="px-1 py-1">
        <input
          {...text('quantity_packed')}
          inputMode="numeric"
          aria-label={`新的第 ${n} 列：已打包數量`}
          aria-invalid={problems.includes('quantity_packed')}
          placeholder="已打包"
          className={`${field} min-w-16 tabular-nums ${problems.includes('quantity_packed') ? bad : ''}`}
        />
      </td>
      <td className="px-1 py-1">
        <Choice
          value={draft.status}
          options={STATUSES}
          labels={STATUS_LABELS}
          tone={STATUS_TONES[draft.status]}
          label={`新的第 ${n} 列：打包狀態`}
          onChange={set('status')}
        />
      </td>
      <td className="px-1 py-1">
        <Choice
          value={draft.check}
          options={CHECK_STATES}
          labels={CHECK_LABELS}
          tone={CHECK_TONES[draft.check]}
          label={`新的第 ${n} 列：Double Check`}
          onChange={set('check')}
        />
      </td>
      <td className="px-1 py-1">
        <Choice
          value={draft.timing}
          options={TIMINGS}
          labels={TIMING_LABELS}
          tone={TIMING_TONES[draft.timing]}
          label={`新的第 ${n} 列：打包時機`}
          onChange={set('timing')}
        />
      </td>
      <td className="px-1 py-1">
        <Choice
          value={draft.need}
          options={NEED_OPTIONS}
          labels={NEED_OPTION_LABELS}
          tone={NEED_TONES[draft.need]}
          label={`新的第 ${n} 列：需求`}
          onChange={set('need')}
        />
      </td>
      <td className="px-1 py-1">
        <Combobox
          value={draft.location}
          onChange={set('location')}
          options={locations}
          aria-label={`新的第 ${n} 列：取得地點`}
          placeholder="取得地點"
          className={`${field} ${toneClass(toneForText(draft.location.trim()))}`}
        />
      </td>
      <td className="px-1 py-1">
        <input {...text('notes')} aria-label={`新的第 ${n} 列：備註`} placeholder="備註" className={field} />
      </td>
      <td className="text-center">
        <button
          type="button"
          onClick={onRemove}
          aria-label={`移除新的第 ${n} 列`}
          className="px-2 text-text-faint hover:text-danger"
          style={{ minHeight: 0 }}
        >
          ✕
        </button>
      </td>
    </tr>
  )
}

export function NewRows({ cellCount, firstNumber, categories, locations, saving, onSave }) {
  const [drafts, setDrafts] = useState([])
  const [showProblems, setShowProblems] = useState(false)

  // A new row starts in the category of the row above it, since rows are
  // usually added a group at a time.
  const addRow = () =>
    setDrafts((current) => [
      ...current.map((draft) => ({ ...draft, autoFocus: false })),
      { ...emptyDraft(current.at(-1)?.category ?? ''), autoFocus: true },
    ])

  const filled = drafts.filter((draft) => !isBlank(draft))
  const blocked = filled.some((draft) => draftProblems(draft).length > 0)

  const save = async () => {
    if (filled.length === 0) return
    if (blocked) {
      setShowProblems(true)
      return
    }
    try {
      await onSave(filled.map(toPayload))
      setDrafts([])
      setShowProblems(false)
    } catch {
      // The rows stay, so nothing typed is lost; the error shows above.
    }
  }

  if (drafts.length === 0) {
    return (
      <tbody>
        <tr className="border-t border-border">
          <td colSpan={cellCount} className="border-b border-border">
            <button
              type="button"
              onClick={addRow}
              className="w-full px-2 py-2 text-left text-sm text-text-faint hover:bg-brand-soft"
              style={{ minHeight: 0 }}
            >
              ▸ 新增一列…
            </button>
          </td>
        </tr>
      </tbody>
    )
  }

  return (
    <tbody
      className="border-2 border-dashed border-brand/50 bg-brand-soft"
      onKeyDown={(event) => {
        if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
          event.preventDefault()
          save()
        }
      }}
    >
      {drafts.map((draft, index) => (
        <DraftRow
          key={draft.key}
          draft={draft}
          index={index}
          number={firstNumber + index}
          showProblems={showProblems && !isBlank(draft)}
          categories={categories}
          locations={locations}
          onChange={(next) =>
            setDrafts((current) => current.map((each) => (each.key === draft.key ? next : each)))
          }
          onRemove={() => setDrafts((current) => current.filter((each) => each.key !== draft.key))}
        />
      ))}
      <tr>
        <td colSpan={cellCount} className="px-2 py-2">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={addRow}
              className="rounded-md border border-border-strong px-3 text-sm text-text-muted"
              style={{ minHeight: 36 }}
            >
              ＋ 再加一列
            </button>
            <button
              type="button"
              onClick={save}
              disabled={saving || filled.length === 0}
              className="rounded-md bg-brand px-4 text-sm font-medium text-on-brand disabled:opacity-50"
              style={{ minHeight: 36 }}
            >
              {saving ? '儲存中…' : `儲存 ${filled.length} 列`}
            </button>
            <button
              type="button"
              onClick={() => {
                setDrafts([])
                setShowProblems(false)
              }}
              className="px-3 text-sm text-text-muted"
              style={{ minHeight: 36 }}
            >
              取消
            </button>
            {showProblems && blocked && (
              <span role="alert" className="text-xs text-danger">
                每一列都要有項目，數量要是整數。
              </span>
            )}
          </div>
        </td>
      </tr>
    </tbody>
  )
}
