import { useRef } from 'react'

/**
 * Long-press without a library: pointer down starts a timer, up or leave
 * cancels it. `consumeClick()` tells the click handler that fires after a
 * long-press to do nothing, so one gesture never does both things.
 *
 * `onPointerCancel` cancels too: a touch that turns into a scroll ends in a
 * cancel rather than an up, and must not open a menu under the finger.
 */
export function useLongPress(onLongPress, { ms = 500 } = {}) {
  const timer = useRef(null)
  const fired = useRef(false)

  const start = (event) => {
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
      onPointerCancel: cancel,
      onContextMenu: (event) => event.preventDefault(),
    },
    consumeClick: () => {
      const was = fired.current
      fired.current = false
      return was
    },
  }
}
