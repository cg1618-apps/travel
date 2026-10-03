/**
 * One row of the sheet, and the status cell that is the only one a tap
 * changes without opening an editor.
 *
 * Split out of `Grid.jsx` so the sheet file holds the table's shape — columns,
 * groups, filters, adding — and this one holds what a single row does. The
 * row is a sortable item: its grip, in the first cell, drags it within its
 * 類別. Value columns are tinted by `lib/tones.js`.
 */

import { useCallback, useState } from 'react'

import { useLongPress } from '../hooks/useLongPress'
import { TIMINGS } from '../lib/timing'
import {
  CHECK_FIELDS,
  CHECK_LABELS,
  CHECK_STATES,
  NEED_LABELS,
  NEEDS,
  STATUS_LABELS,
  TIMING_LABELS,
  checkState,
} from '../lib/labels'
import { itemTitle, rowActions } from '../lib/rowMenu'
import { tapStatus } from '../lib/status'
import { CHECK_TONES, NEED_TONES, STATUS_TONES, TIMING_TONES, toneClass, toneForText } from '../lib/tones'
import { PackedCountCell, QuantityCell, SelectCell, TextCell } from './Cell'
import { RowMenu } from './RowMenu'
import { DragHandle, SortableItem } from './Sortable'

const NEED_OPTIONS = ['', ...NEEDS]
const NEED_OPTION_LABELS = { '': '—', ...NEED_LABELS }

/**
 * Three stored, two tapped: a tap toggles 未打包 ⇄ 已打包 (and brings 不需打包
 * back to 未打包); 不需打包 itself is a long-press or the ⋯ menu away.
 */
function StatusCell({ item, onPatch, onMenu }) {
  const press = useLongPress(onMenu)
  return (
    <button
      type="button"
      {...press.handlers}
      onClick={(event) => {
        if (press.consumeClick(event)) return
        onPatch(item.id, { status: tapStatus(item.status) })
      }}
      aria-label={`${itemTitle(item)}：${STATUS_LABELS[item.status]}，點一下切換`}
      title="點一下切換，長按開啟選單"
      className={`w-full bg-transparent px-2 py-1.5 text-left text-sm select-none ${
        item.status === 'no_need' ? 'line-through' : ''
      }`}
      style={{ minHeight: 0, WebkitTouchCallout: 'none' }}
    >
      {STATUS_LABELS[item.status]}
    </button>
  )
}

const cell = 'border-r border-border'

export function GridRow({
  item,
  showCategory,
  showName,
  continuesRun,
  sortLabel,
  categories,
  locations,
  onPatch,
  onDelete,
  onAddVariant,
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const openMenu = useCallback(() => setMenuOpen(true), [])
  const closeMenu = useCallback(() => setMenuOpen(false), [])
  const patch = (changes) => onPatch(item.id, changes)

  return (
    <SortableItem
      id={item.id}
      as="tr"
      className={`border-t ${continuesRun ? 'border-border/40' : 'border-border'} ${
        item.status === 'no_need' ? 'text-text-faint' : ''
      }`}
    >
      <td className="text-center">
        <DragHandle label={sortLabel} />
      </td>
      <td className={cell}>
        <TextCell
          value={item.category}
          blank={!showCategory}
          placeholder="—"
          options={categories}
          onCommit={(category) => patch({ category })}
        />
      </td>
      <td className="border-r border-border/40">
        <TextCell
          value={item.name}
          blank={!showName}
          placeholder="（未命名）"
          onCommit={(name) => name && patch({ name })}
        />
      </td>
      <td className={cell}>
        <TextCell value={item.detail} placeholder="" onCommit={(detail) => patch({ detail })} />
      </td>
      <td className={cell}>
        <QuantityCell item={item} onCommit={patch} />
      </td>
      <td className={cell}>
        <PackedCountCell
          item={item}
          onCommit={(quantity_packed) => patch({ quantity_packed })}
        />
      </td>
      <td className={`${cell} ${toneClass(STATUS_TONES[item.status])}`}>
        <StatusCell item={item} onPatch={onPatch} onMenu={openMenu} />
      </td>
      <td className={`${cell} ${toneClass(CHECK_TONES[checkState(item)])}`}>
        <SelectCell
          value={checkState(item)}
          options={CHECK_STATES}
          labels={CHECK_LABELS}
          ariaLabel={`${itemTitle(item)}：Double Check`}
          onCommit={(state) => patch(CHECK_FIELDS[state])}
        />
      </td>
      <td className={`${cell} ${toneClass(TIMING_TONES[item.timing])}`}>
        <SelectCell
          value={item.timing}
          options={TIMINGS}
          labels={TIMING_LABELS}
          ariaLabel={`${itemTitle(item)}：打包時機`}
          onCommit={(timing) => patch({ timing })}
        />
      </td>
      <td className={`${cell} ${toneClass(NEED_TONES[item.need])}`}>
        <SelectCell
          value={item.need}
          options={NEED_OPTIONS}
          labels={NEED_OPTION_LABELS}
          ariaLabel={`${itemTitle(item)}：需求`}
          onCommit={(need) => patch({ need })}
        />
      </td>
      <td className={`${cell} ${toneClass(toneForText(item.location))}`}>
        <TextCell
          value={item.location}
          placeholder="—"
          options={locations}
          onCommit={(location) => patch({ location })}
        />
      </td>
      <td className={cell}>
        <TextCell value={item.notes} placeholder="—" onCommit={(notes) => patch({ notes })} />
      </td>
      <td className="text-center">
        <button
          type="button"
          onClick={openMenu}
          aria-label={`${itemTitle(item)} 的選單`}
          aria-haspopup="menu"
          className="px-2 py-1.5 text-text-faint hover:text-text"
          style={{ minHeight: 0 }}
        >
          ⋯
        </button>
        <RowMenu
          open={menuOpen}
          onClose={closeMenu}
          actions={rowActions(item, { onPatch, onAddVariant, onDelete })}
        />
      </td>
    </SortableItem>
  )
}
