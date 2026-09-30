/**
 * The same list with everything taken away except ticking things off.
 *
 * Google Tasks' shape: a tick, a name, a quiet second line, one place to add,
 * and finished things folded out of the way. Nothing here is edited in place
 * — the sheet is where a list is planned, this is where it is worked through.
 *
 * An item with variants (鑰匙: 家鑰匙, 宿舍鑰匙) is its name once, with each
 * variant beneath and its own tick. The tick only ever means packed; 不需打包,
 * Double Check and the rest are a long-press on it, or the ⋯, away.
 */

import { useCallback, useState } from 'react'

import { useLongPress } from '../hooks/useLongPress'
import { groupForChecklist } from '../lib/grouping'
import { NEED_LABELS, STATUS_LABELS } from '../lib/labels'
import { itemTitle, rowActions } from '../lib/rowMenu'
import { tapStatus } from '../lib/status'
import { RowMenu } from './RowMenu'

function quietLine(item) {
  const quantity =
    item.quantity !== null &&
    `已打包 ${item.quantity_packed} / ${item.quantity}${item.unit ?? ''}`
  return [NEED_LABELS[item.need], item.location, quantity, item.notes]
    .filter(Boolean)
    .join(' · ')
}

function Tick({ item, onPatch, onMenu }) {
  const press = useLongPress(onMenu)
  const packed = item.status === 'packed'
  return (
    <button
      type="button"
      {...press.handlers}
      onClick={(event) => {
        if (press.consumeClick(event)) return
        onPatch(item.id, { status: tapStatus(item.status) })
      }}
      aria-label={`${itemTitle(item)}：${STATUS_LABELS[item.status]}，點一下切換`}
      className="shrink-0 px-4 py-3 text-lg text-text-faint select-none"
      style={{ WebkitTouchCallout: 'none' }}
    >
      <span className={packed ? 'text-brand' : ''}>
        {item.status === 'no_need' ? '⊘' : packed ? '☑' : '☐'}
      </span>
    </button>
  )
}

/** One tickable line: a whole item, or one variant of a group. */
function Line({ item, label, withMenu, onPatch }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const openMenu = useCallback(() => setMenuOpen(true), [])
  const closeMenu = useCallback(() => setMenuOpen(false), [])

  const outstanding = item.needs_double_check && !item.double_checked
  const short = item.quantity !== null && item.quantity_packed < item.quantity
  const quiet = quietLine(item)

  return (
    <div className="flex items-start">
      <Tick item={item} onPatch={onPatch} onMenu={openMenu} />

      <div className="min-w-0 flex-1 py-3">
        <p
          className={`m-0 ${
            item.status === 'no_need' ? 'text-text-faint line-through' : ''
          } ${item.status === 'packed' ? 'text-text-muted' : ''}`}
        >
          {label}
        </p>
        {(quiet || outstanding) && (
          <p className="m-0 mt-0.5 text-xs text-text-faint">
            {short && <span className="text-warning">⚠ </span>}
            {quiet}
            {outstanding && (
              <button
                type="button"
                onClick={() => onPatch(item.id, { double_checked: true })}
                className="ml-2 text-warning underline"
                style={{ minHeight: 0 }}
              >
                待確認
              </button>
            )}
          </p>
        )}
      </div>

      <button
        type="button"
        onClick={openMenu}
        aria-label={`${itemTitle(item)} 的選單`}
        aria-haspopup="menu"
        className="shrink-0 px-4 text-text-faint"
      >
        ⋯
      </button>
      <RowMenu open={menuOpen} onClose={closeMenu} actions={withMenu(item)} />
    </div>
  )
}

function Group({ group, withMenu, onPatch }) {
  if (group.items.length === 1) {
    const [item] = group.items
    return (
      <li className="border-b border-border last:border-b-0">
        <Line item={item} label={itemTitle(item)} withMenu={withMenu} onPatch={onPatch} />
      </li>
    )
  }
  return (
    <li className="border-b border-border last:border-b-0">
      <p className="m-0 px-4 pt-3 text-sm font-semibold">{group.name}</p>
      <ul className="list-none p-0 pl-6">
        {group.items.map((item) => (
          <li key={item.id}>
            <Line
              item={item}
              label={item.detail || item.name}
              withMenu={withMenu}
              onPatch={onPatch}
            />
          </li>
        ))}
      </ul>
    </li>
  )
}

function Groups({ items, withMenu, onPatch }) {
  return (
    <ul className="list-none p-0">
      {groupForChecklist(items).map((group) => (
        <Group key={group.key} group={group} withMenu={withMenu} onPatch={onPatch} />
      ))}
    </ul>
  )
}

export function Checklist({ items, onPatch, onAdd, onAddVariant, onDelete }) {
  const [adding, setAdding] = useState('')
  const [showDone, setShowDone] = useState(false)

  const todo = items.filter((item) => item.status === 'not_packed')
  const done = items.filter((item) => item.status !== 'not_packed')
  const withMenu = (item) =>
    rowActions(item, { onPatch, onAddVariant, onDelete, withChecks: true })

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
          {items.length === 0 ? '清單還是空的，從下面新增第一項。' : '全部都處理好了。'}
        </p>
      ) : (
        <Groups items={todo} withMenu={withMenu} onPatch={onPatch} />
      )}

      <form onSubmit={submit} className="border-t border-border">
        <input
          value={adding}
          onChange={(event) => setAdding(event.target.value)}
          placeholder="⊕ 新增項目"
          aria-label="新增項目"
          className="w-full bg-transparent px-4 py-3 outline-none placeholder:text-text-faint focus:bg-brand-soft"
        />
      </form>

      {done.length > 0 && (
        <>
          <button
            type="button"
            onClick={() => setShowDone((open) => !open)}
            aria-expanded={showDone}
            className="w-full border-t border-border px-4 py-2 text-left text-xs font-semibold tracking-wide text-text-faint"
          >
            {showDone ? '▾' : '▸'} 已完成 ({done.length})
          </button>
          {showDone && <Groups items={done} withMenu={withMenu} onPatch={onPatch} />}
        </>
      )}
    </div>
  )
}
