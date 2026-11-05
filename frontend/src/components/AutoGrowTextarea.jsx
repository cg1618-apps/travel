/**
 * A textarea as tall as its text, growing and shrinking while you type, so
 * nothing in a remark scrolls out of sight. `rows` is its smallest height.
 * Every multi-line field in the app is one of these.
 */

import { useLayoutEffect, useRef } from 'react'

export function AutoGrowTextarea({ value, rows = 1, className = '', ...props }) {
  const ref = useRef(null)

  // On the value rather than on the change event, so the text it opens with
  // fits too. Before paint, so a new line never shows a frame of scrolling.
  useLayoutEffect(() => {
    const element = ref.current
    element.style.height = 'auto'
    // scrollHeight leaves out the border, which a border-box height includes.
    const border = element.offsetHeight - element.clientHeight
    element.style.height = `${element.scrollHeight + border}px`
  }, [value])

  return (
    <textarea
      ref={ref}
      rows={rows}
      value={value}
      className={`block resize-none overflow-hidden ${className}`}
      {...props}
    />
  )
}
