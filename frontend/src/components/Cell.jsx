/**
 * A spreadsheet cell: shows a value, becomes an input when you click it.
 *
 * Commit on Enter or blur, revert on Escape — the bargain every spreadsheet
 * makes, so nobody has to be told. There is no Save button anywhere in the
 * grid for the same reason.
 */

import { useRef, useState } from 'react'

import { keysFor } from '../lib/keys'
import { parseWholeNumber } from '../lib/numbers'
import { Combobox } from './Combobox'

const base =
  'w-full bg-transparent px-2 py-1.5 text-left text-sm outline-none focus:bg-brand-soft'

function useCommit(initial, onCommit, onDone) {
  const [value, setValue] = useState(initial)

  const commit = () => {
    onDone()
    if (value !== initial) onCommit(value)
  }

  const onKeyDown = (event) => {
    if (event.key === 'Enter') {
      event.preventDefault()
      commit()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      // Revert: close without committing. Escape has to be safe, because it
      // is what people press when they realise they clicked the wrong cell.
      onDone()
    }
  }

  return { value, setValue, commit, onKeyDown }
}

/**
 * `blank` shows nothing while keeping the value: the sheet's grouping writes a
 * category or a name once per run, and clicking a blank cell beneath still
 * opens the editor on the value the row really holds. `options` makes the
 * editor suggest as you type (`Combobox`).
 */
export function TextCell({ value, placeholder, blank = false, options = [], onCommit }) {
  const [editing, setEditing] = useState(false)

  if (!editing) {
    return (
      <button type="button" onClick={() => setEditing(true)} className={base}>
        {blank ? null : value || <span className="text-text-faint">{placeholder}</span>}
      </button>
    )
  }

  return <TextInput value={value} options={options} onCommit={onCommit} onDone={() => setEditing(false)} />
}

function TextInput({ value, options, onCommit, onDone }) {
  const initial = value ?? ''
  const [text, setText] = useState(initial)
  // Enter closes the editor, and closing it blurs the input: without this the
  // one edit would be committed twice.
  const finished = useRef(false)

  const commit = (next) => {
    if (finished.current) return
    finished.current = true
    onDone()
    if (next !== initial) onCommit(next.trim() || null)
  }
  const revert = () => {
    // Close without committing. Escape has to be safe, because it is what
    // people press when they realise they clicked the wrong cell.
    finished.current = true
    onDone()
  }
  const onKeyDown = (event) => keysFor(() => commit(text), revert)(event)
  const props = {
    // autoFocus rather than a ref and an effect: the input is mounted by the
    // click that opened the cell, so focusing on mount IS the behaviour, and
    // selecting on focus makes overtyping the default.
    autoFocus: true,
    onFocus: (event) => event.target.select(),
    onBlur: () => commit(text),
    onKeyDown,
    className: `${base} bg-surface ring-1 ring-brand`,
  }

  if (options.length === 0) {
    return <input {...props} value={text} onChange={(event) => setText(event.target.value)} />
  }
  return <Combobox {...props} value={text} onChange={setText} options={options} onPick={commit} />
}

/**
 * 數量: the target and its unit, one cell — "5 雙" is one fact. How many are
 * already packed is its own column, 已打包數量, as in the sheet.
 */
export function QuantityCell({ item, onCommit }) {
  const [editing, setEditing] = useState(false)

  if (!editing) {
    return (
      <button type="button" onClick={() => setEditing(true)} className={`${base} tabular-nums`}>
        {item.quantity === null ? (
          <span className="text-text-faint">—</span>
        ) : (
          <>
            {item.quantity}
            {item.unit ? ` ${item.unit}` : ''}
          </>
        )}
      </button>
    )
  }

  return <QuantityInput item={item} onCommit={onCommit} onDone={() => setEditing(false)} />
}

function QuantityInput({ item, onCommit, onDone }) {
  const [target, setTarget] = useState(item.quantity === null ? '' : String(item.quantity))
  const [unit, setUnit] = useState(item.unit ?? '')

  const commit = () => {
    onDone()
    const quantity = parseWholeNumber(target)
    // Not a whole number: the cell reverts and sends nothing, unit included,
    // the way 價錢 refuses a typo — "1.5" would only come back as a 422.
    if (quantity === undefined) return
    const nextUnit = unit.trim() || null
    if (quantity !== item.quantity || nextUnit !== (item.unit ?? null)) {
      onCommit({ quantity, unit: nextUnit })
    }
  }
  const onKeyDown = (event) => {
    if (event.key === 'Enter') {
      event.preventDefault()
      commit()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      onDone()
    }
  }

  return (
    <div
      className="flex items-center gap-1 bg-surface px-1 ring-1 ring-brand"
      // Moving between the two inputs is not leaving the cell.
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) commit()
      }}
    >
      <input
        autoFocus
        // Text with a numeric keypad, as 價錢 is: a number input reports
        // anything it cannot parse as '', which would clear the quantity
        // instead of refusing the typo.
        inputMode="numeric"
        value={target}
        onChange={(event) => setTarget(event.target.value)}
        onKeyDown={onKeyDown}
        aria-label="數量"
        placeholder="—"
        className="w-12 bg-transparent py-1.5 text-sm tabular-nums outline-none"
      />
      <input
        value={unit}
        onChange={(event) => setUnit(event.target.value)}
        onKeyDown={onKeyDown}
        aria-label="單位"
        placeholder="單位"
        className="w-12 bg-transparent py-1.5 text-sm outline-none"
      />
    </div>
  )
}

/**
 * 已打包數量. Unset until someone counts, and shown as — like 數量, so a blank
 * never reads as "none packed". Short of 數量 is marked once there is a
 * count, because being short is the failure a packing list exists to catch.
 */
export function PackedCountCell({ item, onCommit }) {
  const [editing, setEditing] = useState(false)
  const packed = item.quantity_packed ?? null
  const short = item.quantity !== null && packed !== null && packed < item.quantity

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => setEditing(true)}
        className={`${base} tabular-nums ${short ? 'text-warning' : ''}`}
        title={short ? '少於數量' : undefined}
      >
        {packed === null ? <span className="text-text-faint">—</span> : packed}
      </button>
    )
  }

  return (
    <PackedCountInput
      value={packed === null ? '' : String(packed)}
      onCommit={(next) => {
        // An emptied cell clears the count; anything that is not a whole
        // number reverts, as 數量 does.
        const parsed = parseWholeNumber(next)
        if (parsed !== undefined) onCommit(parsed)
      }}
      onDone={() => setEditing(false)}
    />
  )
}

function PackedCountInput({ value, onCommit, onDone }) {
  const cell = useCommit(value, onCommit, onDone)
  return (
    <input
      autoFocus
      inputMode="numeric"
      onFocus={(event) => event.target.select()}
      value={cell.value}
      onChange={(event) => cell.setValue(event.target.value)}
      onBlur={cell.commit}
      onKeyDown={cell.onKeyDown}
      aria-label="已打包數量"
      className={`${base} bg-surface tabular-nums ring-1 ring-brand`}
    />
  )
}

/**
 * A closed vocabulary. An empty option ('') stands for null, so a column that
 * may be unset (需求) is the same control as one that may not (打包時機).
 */
export function SelectCell({ value, options, labels, onCommit, ariaLabel }) {
  return (
    <select
      value={value ?? ''}
      onChange={(event) => onCommit(event.target.value === '' ? null : event.target.value)}
      aria-label={ariaLabel}
      className={`${base} cursor-pointer appearance-none`}
    >
      {options.map((option) => (
        <option key={option} value={option}>
          {labels[option]}
        </option>
      ))}
    </select>
  )
}
