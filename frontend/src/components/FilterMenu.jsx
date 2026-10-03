/**
 * A column header's filter: Google Sheets' "filter by values", a tick per
 * value. Nothing ticked is no filter. Each value carries its tone, so the
 * list reads like the column it filters.
 *
 * Portaled and fixed under its button, like `RowMenu`, so the sheet's scroll
 * container cannot clip it. Escape or a click outside closes it.
 */

import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import { FILTERS } from '../lib/filters'
import { toneClass } from '../lib/tones'

export function FilterMenu({ column, label, items, selected, toneFor, onToggle, onClear }) {
  const button = useRef(null)
  const panel = useRef(null)
  const [open, setOpen] = useState(false)
  const [place, setPlace] = useState(null)
  const filter = FILTERS[column]
  const active = selected.length > 0

  useLayoutEffect(() => {
    if (!open || !button.current) return
    const rect = button.current.getBoundingClientRect()
    setPlace({ top: rect.bottom + 4, left: Math.min(rect.left, window.innerWidth - 220) })
  }, [open])

  useEffect(() => {
    if (!open) return undefined
    const onPointerDown = (event) => {
      if (!panel.current?.contains(event.target) && !button.current?.contains(event.target)) {
        setOpen(false)
      }
    }
    const onKeyDown = (event) => {
      if (event.key === 'Escape') setOpen(false)
    }
    const close = () => setOpen(false)
    // The panel is fixed where its button was; once the page moves under it,
    // it is pointing at nothing. Its own list scrolling is not that.
    const onScroll = (event) => {
      if (!panel.current?.contains(event.target)) setOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown, true)
    document.addEventListener('keydown', onKeyDown)
    window.addEventListener('resize', close)
    window.addEventListener('scroll', onScroll, true)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown, true)
      document.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('resize', close)
      window.removeEventListener('scroll', onScroll, true)
    }
  }, [open])

  return (
    <>
      <button
        ref={button}
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={`篩選${label}${active ? `（已選 ${selected.length} 項）` : ''}`}
        title="篩選"
        className={`flex w-full items-center justify-between gap-1 text-left ${
          active ? 'text-brand' : ''
        }`}
        style={{ minHeight: 0 }}
      >
        {label}
        <span aria-hidden="true" className={active ? 'text-brand' : 'text-text-faint'}>
          {active ? '▼' : '▾'}
        </span>
      </button>
      {open &&
        place &&
        createPortal(
          <div
            ref={panel}
            role="dialog"
            aria-label={`篩選${label}`}
            style={place}
            className="fixed z-50 w-52 rounded-md border border-border bg-surface p-2 text-sm shadow-lg"
          >
            <ul className="m-0 max-h-64 list-none overflow-y-auto p-0">
              {filter.values(items).map((value) => (
                <li key={value}>
                  <label className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1 hover:bg-surface-2">
                    <input
                      type="checkbox"
                      checked={selected.includes(value)}
                      onChange={() => onToggle(value)}
                    />
                    <span className={`rounded-sm px-1.5 ${toneClass(toneFor(value))}`}>
                      {filter.label(value)}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
            <button
              type="button"
              onClick={onClear}
              disabled={!active}
              className="mt-1 w-full rounded-sm px-2 text-left text-xs text-text-muted hover:bg-surface-2 disabled:opacity-40"
              style={{ minHeight: 32 }}
            >
              清除這欄的篩選
            </button>
          </div>,
          document.body,
        )}
    </>
  )
}
