import { useEffect, useRef } from 'react'

/**
 * Long-press without a library: pointer down starts a timer, up or leave
 * cancels it. `consumeClick()` tells the click handler that fires after a
 * long-press to do nothing, so one gesture never does both things.
 *
 * `onPointerCancel` cancels too: a touch that turns into a scroll ends in a
 * cancel rather than an up, and must not open a menu under the finger. A
 * cancelled gesture produces no click, so it also forgets that a long-press
 * fired — otherwise the next click, from anything, would be swallowed.
 *
 * `consumeClick(event)` never swallows a keyboard click (`event.detail === 0`):
 * Enter or Space is not the tail of a pointer gesture.
 */
export function useLongPress(onLongPress, { ms = 500 } = {}) {
  const timer = useRef(null)
  const fired = useRef(false)

  // A timer outliving its component would call into a row that is gone.
  useEffect(() => () => clearTimeout(timer.current), [])

  const start = (event) => {
    clearTimeout(timer.current)
    fired.current = false
    timer.current = setTimeout(() => {
      fired.current = true
      onLongPress(event)
    }, ms)
  }
  const cancel = () => clearTimeout(timer.current)

  return {
    handlers: {
      onPointerDown: start,
      onPointerUp: cancel,
      onPointerLeave: cancel,
      onPointerCancel: () => {
        cancel()
        fired.current = false
      },
      onContextMenu: (event) => event.preventDefault(),
    },
    consumeClick: (event) => {
      const was = fired.current && event?.detail !== 0
      fired.current = false
      return was
    },
  }
}
