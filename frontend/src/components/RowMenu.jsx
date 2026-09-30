/**
 * A row's ⋯ menu: the things one tap does not do.
 *
 * Anchored beside the row on a wide screen, a bottom sheet on a phone — the
 * same split `EvictDialog` makes, because a popover under a thumb is covered
 * by the thumb. It renders into `document.body` so the sheet's horizontal
 * scroll container cannot clip it; a marker left in place is what it measures
 * its position from.
 */

import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

const MENU_HEIGHT_GUESS = 260
const GUTTER = 8

function placeBeside(marker) {
  const rect = marker.getBoundingClientRect()
  const right = Math.max(GUTTER, window.innerWidth - rect.right)
  // Open upwards when there is no room below, so the last rows' menus are
  // not pushed off the bottom of the screen.
  return rect.bottom + MENU_HEIGHT_GUESS > window.innerHeight
    ? { '--menu-top': 'auto', '--menu-bottom': `${window.innerHeight - rect.top}px`, '--menu-right': `${right}px` }
    : { '--menu-top': `${rect.bottom}px`, '--menu-bottom': 'auto', '--menu-right': `${right}px` }
}

export function RowMenu({ open, onClose, actions }) {
  const marker = useRef(null)
  const menu = useRef(null)
  const [place, setPlace] = useState(null)

  useLayoutEffect(() => {
    if (open && marker.current) setPlace(placeBeside(marker.current))
  }, [open])

  useEffect(() => {
    if (!open) return undefined
    menu.current?.querySelector('[role="menuitem"]')?.focus()
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  return (
    <>
      <span ref={marker} className="block h-0 w-0" aria-hidden="true" />
      {open &&
        createPortal(
          <div className="fixed inset-0 z-50">
            <div
              className="absolute inset-0 bg-ink/50 sm:bg-transparent"
              onClick={onClose}
              aria-hidden="true"
            />
            <div
              ref={menu}
              role="menu"
              style={place ?? undefined}
              className="absolute inset-x-0 bottom-0 rounded-t-2xl border border-border bg-surface p-2 shadow-lg sm:inset-x-auto sm:top-(--menu-top) sm:right-(--menu-right) sm:bottom-(--menu-bottom) sm:w-56 sm:rounded-md"
            >
              {actions.map((action) => (
                <button
                  key={action.label}
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    onClose()
                    action.onSelect()
                  }}
                  className={`block w-full rounded-sm px-3 text-left text-sm hover:bg-surface-2 focus:bg-surface-2 focus:outline-none ${
                    action.danger ? 'text-danger' : 'text-text'
                  }`}
                >
                  {action.label}
                </button>
              ))}
            </div>
          </div>,
          document.body,
        )}
    </>
  )
}
