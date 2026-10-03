/**
 * A text input that suggests as you type: 類別, 取得地點, 車票類型.
 *
 * Replaces the browser's `<datalist>`, which only opened from its triangle
 * and drew a native popup that looked like no other part of the app. This
 * one opens on focus and narrows with every keystroke. The suggestions are
 * only suggestions: whatever is typed is still what is kept, and Enter with
 * nothing highlighted commits the typed text, not the first match.
 *
 * The list renders into `document.body`, positioned under the input, so the
 * sheet's scroll container cannot clip it — the same reason `RowMenu` does.
 */

import { useId, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import { suggest } from '../lib/suggest'

const LIST_MAX_HEIGHT = 240

function placeUnder(input) {
  const rect = input.getBoundingClientRect()
  const below = window.innerHeight - rect.bottom
  const up = below < LIST_MAX_HEIGHT && rect.top > below
  return {
    left: rect.left,
    minWidth: Math.max(rect.width, 160),
    ...(up ? { bottom: window.innerHeight - rect.top + 2 } : { top: rect.bottom + 2 }),
  }
}

export function Combobox({ value, onChange, options, onPick, onKeyDown, onBlur, className, ...rest }) {
  const input = useRef(null)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const [place, setPlace] = useState(null)
  const listId = useId()

  const matches = suggest(options, value)
  const showing = open && matches.length > 0

  useLayoutEffect(() => {
    if (!showing) return undefined
    const update = () => input.current && setPlace(placeUnder(input.current))
    update()
    // Capture: the sheet scrolls inside its own container, not the window.
    window.addEventListener('scroll', update, true)
    window.addEventListener('resize', update)
    return () => {
      window.removeEventListener('scroll', update, true)
      window.removeEventListener('resize', update)
    }
  }, [showing])

  const pick = (option) => {
    setOpen(false)
    setActive(-1)
    onChange(option)
    onPick?.(option)
  }

  const handleKeyDown = (event) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      if (!open) {
        setOpen(true)
        return
      }
      const step = event.key === 'ArrowDown' ? 1 : -1
      setActive((current) => Math.max(-1, Math.min(matches.length - 1, current + step)))
      return
    }
    if (event.key === 'Enter' && showing && active >= 0) {
      event.preventDefault()
      pick(matches[active])
      return
    }
    if (event.key === 'Escape' && showing) {
      // The first Escape closes the suggestions; the next one is the cell's.
      event.preventDefault()
      setOpen(false)
      return
    }
    if (event.key === 'Tab') setOpen(false)
    onKeyDown?.(event)
  }

  return (
    <>
      <input
        ref={input}
        {...rest}
        value={value}
        role="combobox"
        aria-expanded={showing}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={showing && active >= 0 ? `${listId}-${active}` : undefined}
        autoComplete="off"
        onFocus={(event) => {
          setOpen(true)
          rest.onFocus?.(event)
        }}
        onChange={(event) => {
          onChange(event.target.value)
          setOpen(true)
          setActive(-1)
        }}
        onKeyDown={handleKeyDown}
        onBlur={(event) => {
          setOpen(false)
          onBlur?.(event)
        }}
        className={className}
      />
      {showing &&
        place &&
        createPortal(
          <ul
            id={listId}
            role="listbox"
            style={{ ...place, maxHeight: LIST_MAX_HEIGHT }}
            className="fixed z-50 m-0 list-none overflow-y-auto rounded-md border border-border bg-surface p-1 shadow-lg"
          >
            {matches.map((option, index) => (
              <li
                key={option}
                id={`${listId}-${index}`}
                role="option"
                aria-selected={index === active}
                // mousedown, not click: a click would blur the input first,
                // and the blur commits whatever was typed before the pick.
                onMouseDown={(event) => {
                  event.preventDefault()
                  pick(option)
                }}
                onMouseEnter={() => setActive(index)}
                className={`cursor-pointer rounded-sm px-3 py-1.5 text-sm whitespace-nowrap ${
                  index === active ? 'bg-brand-soft text-brand' : 'text-text'
                }`}
              >
                {option}
              </li>
            ))}
          </ul>,
          document.body,
        )}
    </>
  )
}
