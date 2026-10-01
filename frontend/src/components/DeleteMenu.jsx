/**
 * A ⋯ button and the menu it opens, for the one action a header or card has:
 * deleting it. The confirmation is the caller's, because only the caller knows
 * what else goes with the thing deleted.
 */

import { useState } from 'react'

import { RowMenu } from './RowMenu'

export function DeleteMenu({ label, menuLabel, onSelect }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button
        type="button"
        aria-label={menuLabel}
        aria-haspopup="menu"
        onClick={() => setOpen(true)}
        className="px-2 text-text-faint hover:text-text"
        style={{ minHeight: 0 }}
      >
        ⋯
      </button>
      <RowMenu
        open={open}
        onClose={() => setOpen(false)}
        actions={[{ label, danger: true, onSelect }]}
      />
    </>
  )
}
