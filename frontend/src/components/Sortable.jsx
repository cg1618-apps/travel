/**
 * Drag-to-reorder for a flat list: the rows of one 類別, and the 類別
 * themselves in 排序類別.
 *
 * The media tracker's `components/ui/Sortable.jsx`, with its reasons: built on
 * dnd-kit's pointer events rather than native HTML5 drag, which swallows the
 * mouse wheel on Windows and does nothing on a touch screen. A row is picked
 * up only by its `DragHandle`, so the cells beside it stay clickable, and the
 * handle moves its row one place with ↑ / ↓ for the keyboard.
 *
 *   <SortableList ids={ids} onMove={(from, to) => ...}>
 *     {rows.map((row) => (
 *       <SortableItem key={row.id} id={row.id} as="tr">
 *         <td><DragHandle label={row.name} /></td>
 *       </SortableItem>
 *     ))}
 *   </SortableList>
 *
 * `onMove(from, to)` fires once per drop or key press, with indexes into
 * `ids`; the caller builds the new order.
 */

import { createContext, useContext, useEffect, useMemo, useRef } from 'react'
import { DndContext, PointerSensor, TouchSensor, closestCenter, useSensor, useSensors } from '@dnd-kit/core'
import { SortableContext, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

const ListContext = createContext(null)
const ItemContext = createContext(null)

// A press has to travel a few pixels before it becomes a drag, so a plain
// click on the handle does nothing; on touch a short hold, so a swipe over a
// handle still scrolls the page.
const POINTER = { distance: 4 }
const TOUCH = { delay: 150, tolerance: 6 }

const lockToVerticalAxis = ({ transform }) => ({ ...transform, x: 0 })

const SCREEN_READER = { draggable: '拖曳以排序，或按上下方向鍵移動一格。' }

export function SortableList({ ids, onMove, disabled = false, children }) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: POINTER }),
    useSensor(TouchSensor, { activationConstraint: TOUCH }),
  )
  const handles = useRef(new Map())
  const focusAfterMove = useRef(null)

  // A keyboard move re-renders the row elsewhere; refocus its handle so a held
  // arrow key keeps moving the same row.
  useEffect(() => {
    const id = focusAfterMove.current
    if (id == null) return
    focusAfterMove.current = null
    handles.current.get(id)?.focus()
  })

  const list = useMemo(
    () => ({
      disabled,
      handles,
      moveByKey(id, delta) {
        const from = ids.indexOf(id)
        const to = from + delta
        if (disabled || from < 0 || to < 0 || to >= ids.length) return
        focusAfterMove.current = id
        onMove(from, to)
      },
    }),
    [ids, disabled, onMove],
  )

  const onDragEnd = ({ active, over }) => {
    if (!over || active.id === over.id) return
    const from = ids.indexOf(active.id)
    const to = ids.indexOf(over.id)
    if (from >= 0 && to >= 0) onMove(from, to)
  }

  return (
    <ListContext.Provider value={list}>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        modifiers={[lockToVerticalAxis]}
        // Portaled: dnd-kit's hidden instructions are a <div>, and a sheet's
        // rows sit in a <tbody>, where a <div> is invalid HTML.
        accessibility={{ screenReaderInstructions: SCREEN_READER, container: document.body }}
        onDragEnd={onDragEnd}
      >
        <SortableContext items={ids} strategy={verticalListSortingStrategy} disabled={disabled}>
          {children}
        </SortableContext>
      </DndContext>
    </ListContext.Provider>
  )
}

/** One row. Renders `as` (default div) and carries the drag transform. */
export function SortableItem({ id, as: Tag = 'div', className = '', style, children, ...rest }) {
  const sortable = useSortable({ id })
  const { setNodeRef, transform, transition, isDragging } = sortable
  return (
    <ItemContext.Provider value={{ id, ...sortable }}>
      <Tag
        ref={setNodeRef}
        className={`${className} ${isDragging ? 'relative z-20 bg-surface opacity-90 shadow-lg' : ''}`}
        style={{ ...style, transform: CSS.Translate.toString(transform), transition }}
        {...rest}
      >
        {children}
      </Tag>
    </ItemContext.Provider>
  )
}

/** The grip a row is dragged by; `label` names the row for screen readers. */
export function DragHandle({ label, className = '' }) {
  const list = useContext(ListContext)
  const { id, attributes, listeners, setActivatorNodeRef, isDragging } = useContext(ItemContext)

  const ref = (element) => {
    setActivatorNodeRef(element)
    if (element) list.handles.current.set(id, element)
    else list.handles.current.delete(id)
  }

  const onKeyDown = (event) => {
    if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return
    event.preventDefault()
    list.moveByKey(id, event.key === 'ArrowUp' ? -1 : 1)
  }

  return (
    <button
      type="button"
      ref={ref}
      {...attributes}
      {...listeners}
      onKeyDown={onKeyDown}
      disabled={list.disabled}
      aria-label={`排序「${label}」`}
      title={list.disabled ? '篩選時不能排序' : '拖曳以排序（或按 ↑ / ↓）'}
      className={`shrink-0 touch-none px-1 text-text-faint/60 select-none hover:text-text-faint disabled:cursor-not-allowed disabled:opacity-30 ${
        isDragging ? 'cursor-grabbing' : 'cursor-grab'
      } ${className}`}
      style={{ minHeight: 0 }}
    >
      <span aria-hidden="true">⠿</span>
    </button>
  )
}
