/** The 價錢 cell, shared by Transportation and This time: a whole number shown as `NT$22`. */

import { useState } from 'react'

import { keysFor } from '../lib/keys'
import { parseWholeNumber } from '../lib/numbers'
import { formatPrice } from '../lib/transport'

export function PriceCell({ price, onCommit }) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState('')

  const finish = (save) => {
    setEditing(false)
    if (!save) return
    const next = parseWholeNumber(text)
    if (next !== undefined && next !== price) onCommit(next)
  }

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => {
          setText(price === null ? '' : String(price))
          setEditing(true)
        }}
        className="w-full bg-transparent px-2 py-1.5 text-left text-sm tabular-nums outline-none"
      >
        {formatPrice(price) ?? <span className="text-text-faint">—</span>}
      </button>
    )
  }
  return (
    <input
      autoFocus
      inputMode="numeric"
      aria-label="價錢"
      value={text}
      onFocus={(event) => event.target.select()}
      onChange={(event) => setText(event.target.value)}
      onBlur={() => finish(true)}
      onKeyDown={keysFor(
        () => finish(true),
        () => finish(false),
      )}
      className="w-full bg-surface px-2 py-1.5 text-sm tabular-nums outline-none ring-1 ring-brand"
    />
  )
}
