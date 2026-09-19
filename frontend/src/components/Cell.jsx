/**
 * A spreadsheet cell: shows a value, becomes an input when you click it.
 *
 * Commit on Enter or blur, revert on Escape — the bargain every spreadsheet
 * makes, so nobody has to be told. There is no Save button anywhere in the
 * grid for the same reason.
 */

import { useState } from 'react'

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

export function TextCell({ value, placeholder, options = [], listId, onCommit }) {
  const [editing, setEditing] = useState(false)

  if (!editing) {
    return (
      <button type="button" onClick={() => setEditing(true)} className={base}>
        {value || <span className="text-text-faint">{placeholder}</span>}
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
 * Quantity is two numbers and a unit in one cell: packed of target.
 *
 * They are edited together because they are read together — "3 / 5 pairs" is
 * one fact, and splitting it across three columns would widen the sheet for
 * no gain.
 */
export function QuantityCell({ item, onCommit }) {
  const [editing, setEditing] = useState(false)
  const [packed, setPacked] = useState(String(item.quantity_packed ?? 0))
  const [target, setTarget] = useState(item.quantity === null ? '' : String(item.quantity))
  const [unit, setUnit] = useState(item.unit ?? '')

  if (!editing) {
    const short = item.quantity !== null && item.quantity_packed < item.quantity
    return (
      <button
        type="button"
        onClick={() => setEditing(true)}
        className={`${base} tabular-nums ${short ? 'text-warning' : ''}`}
        title={short ? 'Short of the target' : undefined}
      >
        {item.quantity === null ? (
          <span className="text-text-faint">—</span>
        ) : (
          <>
            {short && <span aria-hidden="true">⚠ </span>}
            {item.quantity_packed} / {item.quantity}
            {item.unit ? ` ${item.unit}` : ''}
          </>
        )}
      </button>
    )
  }

  const commit = () => {
    setEditing(false)
    onCommit({
      quantity_packed: Number(packed) || 0,
      quantity: target === '' ? null : Number(target),
      unit: unit.trim() || null,
    })
  }

  return (
    <div className="flex items-center gap-1 bg-surface px-1 ring-1 ring-brand">
      <input
        autoFocus
        type="number"
        min="0"
        value={packed}
        onChange={(event) => setPacked(event.target.value)}
        onKeyDown={(event) => event.key === 'Enter' && commit()}
        aria-label="Packed"
        className="w-10 bg-transparent py-1.5 text-sm tabular-nums outline-none"
      />
      <span className="text-text-faint">/</span>
      <input
        type="number"
        min="0"
        value={target}
        onChange={(event) => setTarget(event.target.value)}
        onKeyDown={(event) => event.key === 'Enter' && commit()}
        aria-label="How many to pack"
        placeholder="—"
        className="w-10 bg-transparent py-1.5 text-sm tabular-nums outline-none"
      />
      <input
        value={unit}
        onChange={(event) => setUnit(event.target.value)}
        onKeyDown={(event) => event.key === 'Enter' && commit()}
        onBlur={commit}
        aria-label="Unit"
        placeholder="unit"
        className="w-16 bg-transparent py-1.5 text-sm outline-none"
      />
    </div>
  )
}

export function SelectCell({ value, options, labels, onCommit }) {
  return (
    <select
      value={value}
      onChange={(event) => onCommit(event.target.value)}
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
