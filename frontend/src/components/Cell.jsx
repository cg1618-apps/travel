/**
 * A spreadsheet cell: shows a value, becomes an input when you click it.
 *
 * Commit on Enter or blur, revert on Escape — the bargain every spreadsheet
 * makes, so nobody has to be told. There is no Save button anywhere in the
 * grid for the same reason.
 */

import { useState } from 'react'

import { parseWholeNumber } from '../lib/numbers'

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
 * opens the editor on the value the row really holds.
 */
export function TextCell({ value, placeholder, blank = false, options = [], listId, onCommit }) {
  const [editing, setEditing] = useState(false)

  if (!editing) {
    return (
      <button type="button" onClick={() => setEditing(true)} className={base}>
        {blank ? null : value || <span className="text-text-faint">{placeholder}</span>}
      </button>
    )
  }

  return <TextInput value={value} options={options} listId={listId} onCommit={onCommit} onDone={() => setEditing(false)} />
}

function TextInput({ value, options, listId, onCommit, onDone }) {
  const cell = useCommit(value ?? '', (next) => onCommit(next.trim() || null), onDone)
  return (
    <>
      <input
        // autoFocus rather than a ref and an effect: the input is mounted by
        // the click that opened the cell, so focusing on mount IS the
        // behaviour, and selecting on focus makes overtyping the default.
        autoFocus
        onFocus={(event) => event.target.select()}
        value={cell.value}
        list={options.length ? listId : undefined}
        onChange={(event) => cell.setValue(event.target.value)}
        onBlur={cell.commit}
        onKeyDown={cell.onKeyDown}
        className={`${base} bg-surface ring-1 ring-brand`}
      />
      {options.length > 0 && (
        <datalist id={listId}>
          {options.map((option) => (
            <option key={option} value={option} />
          ))}
        </datalist>
      )}
    </>
  )
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
 * 已打包數量. Short of 數量 is marked, because being short is the failure a
 * packing list exists to catch.
 */
export function PackedCountCell({ item, onCommit }) {
  const [editing, setEditing] = useState(false)
  const short = item.quantity !== null && item.quantity_packed < item.quantity

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => setEditing(true)}
        className={`${base} tabular-nums ${short ? 'text-warning' : ''}`}
        title={short ? '少於數量' : undefined}
      >
        {item.quantity_packed ?? 0}
      </button>
    )
  }

  return (
    <PackedCountInput
      value={String(item.quantity_packed ?? 0)}
      onCommit={(next) => onCommit(Number(next) || 0)}
      onDone={() => setEditing(false)}
    />
  )
}

function PackedCountInput({ value, onCommit, onDone }) {
  const cell = useCommit(value, onCommit, onDone)
  return (
    <input
      autoFocus
      type="number"
      min="0"
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
