/**
 * The same list with everything taken away except ticking things off.
 *
 * Google Tasks' shape: a checkbox, a name, a quiet second line, one place to
 * add, and finished things folded out of the way. Nothing here is editable
 * except the tick — the sheet is where a list is planned, this is where it is
 * worked through, and mixing the two is what made the first attempt confusing.
 */

import { useState } from 'react'

function Line({ item, onPatch }) {
  const done = item.status !== 'not_packed'
  const outstanding = item.needs_double_check && !item.double_checked
  const short = item.quantity !== null && item.quantity_packed < item.quantity

  const detail = [
    item.quantity !== null &&
      `${item.quantity_packed} of ${item.quantity}${item.unit ? ` ${item.unit}` : ''}`,
    item.bag,
    item.notes,
  ].filter(Boolean)

  return (
    <li className="border-b border-border last:border-b-0">
      <div className="flex items-start">
        <button
          type="button"
          onClick={() =>
            onPatch(item.id, { status: done ? 'not_packed' : 'packed' })
          }
          aria-label={done ? `Untick ${item.name}` : `Tick ${item.name}`}
          className="px-4 py-3 text-lg text-text-faint"
        >
          <span className={done ? 'text-brand' : ''}>{done ? '☑' : '☐'}</span>
        </button>

        <div className="min-w-0 flex-1 py-3 pr-4">
          <p
            className={`m-0 ${
              item.status === 'no_need' ? 'text-text-faint line-through' : ''
            } ${item.status === 'packed' ? 'text-text-muted' : ''}`}
          >
            {item.name}
          </p>
          {(detail.length > 0 || outstanding) && (
            <p className="m-0 mt-0.5 text-xs text-text-faint">
              {short && <span className="text-warning">⚠ </span>}
              {detail.join(' · ')}
              {outstanding && (
                <button
                  type="button"
                  onClick={() => onPatch(item.id, { double_checked: true })}
                  className="ml-2 text-warning underline"
                  style={{ minHeight: 0 }}
                >
                  check it
                </button>
              )}
            </p>
          )}
        </div>
      </div>
    </li>
  )
}

export function Checklist({ items, onPatch, onAdd }) {
  const [adding, setAdding] = useState('')
  const [showDone, setShowDone] = useState(false)

  const todo = items.filter((item) => item.status === 'not_packed')
  const done = items.filter((item) => item.status !== 'not_packed')

  const submit = (event) => {
    event.preventDefault()
    if (!adding.trim()) return
    onAdd(adding.trim())
    setAdding('')
  }

  return (
    <div className="border-y border-border bg-surface">
      {todo.length === 0 ? (
        <p className="px-4 py-8 text-center text-sm text-text-muted">
          {items.length === 0
            ? 'Nothing on this list yet. Add the first thing below.'
            : 'Everything is ticked off.'}
        </p>
      ) : (
        <ul className="list-none p-0">
          {todo.map((item) => (
            <Line key={item.id} item={item} onPatch={onPatch} />
          ))}
        </ul>
      )}

      <form onSubmit={submit} className="border-t border-border">
        <input
          value={adding}
          onChange={(event) => setAdding(event.target.value)}
          placeholder="⊕  Add an item"
          aria-label="Add an item"
          className="w-full bg-transparent px-4 py-3 outline-none placeholder:text-text-faint focus:bg-brand-soft"
        />
      </form>

      {done.length > 0 && (
        <>
          <button
            type="button"
            onClick={() => setShowDone((open) => !open)}
            className="w-full border-t border-border px-4 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-faint"
          >
            {showDone ? '▾' : '▸'} Done ({done.length})
          </button>
          {showDone && (
            <ul className="list-none p-0">
              {done.map((item) => (
                <Line key={item.id} item={item} onPatch={onPatch} />
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}
