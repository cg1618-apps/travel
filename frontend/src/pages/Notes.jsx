/**
 * 筆記: notes that belong to no trip or route - a title, a description and
 * links, under a 群組 of their own choosing.
 *
 * Shown grouped, the ungrouped notes first with no heading. The ⠿ beside a
 * note drags it within its group, the ↑ / ↓ on a group's heading move the whole
 * group a place, and the server keeps both as one order
 * (`PUT /api/notes/order`), refusing one that splits a group. A note is added
 * and edited in the same form a route's note uses
 * (`NoteEditor.jsx`), where it also needs a title and can take a 群組; its
 * description is a cell of its own on the card too. Links open in a new tab.
 */

import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { endpoints } from '../api/endpoints'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { DeleteMenu } from '../components/DeleteMenu'
import { NoteBody, NoteForm } from '../components/NoteEditor'
import { DragHandle, SortableItem, SortableList } from '../components/Sortable'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { send, useApiMutation, useApiQuery } from '../hooks/useApiQuery'
import {
  groupByName,
  moveInGroup,
  namedGroups,
  orderAfterGroupSort,
  orderIds,
  reposition,
} from '../lib/grouping'
import { moveBy, noteName } from '../lib/transport'

const KEY = ['notes']
const arrowButton = 'px-2 text-text-faint hover:text-text disabled:opacity-30'

/** A named group's heading; `onMove` is absent when there is nowhere to move it. */
function GroupHeading({ name, onMove, isFirst, isLast, disabled }) {
  return (
    <div className="mb-1 flex items-center gap-1 px-4">
      <h2 className="m-0 text-xs font-semibold uppercase tracking-wide text-text-faint">{name}</h2>
      {onMove && (
        <>
          <button
            type="button"
            aria-label={`上移群組「${name}」`}
            disabled={disabled || isFirst}
            onClick={() => onMove(-1)}
            className={arrowButton}
            style={{ minHeight: 0 }}
          >
            ↑
          </button>
          <button
            type="button"
            aria-label={`下移群組「${name}」`}
            disabled={disabled || isLast}
            onClick={() => onMove(1)}
            className={arrowButton}
            style={{ minHeight: 0 }}
          >
            ↓
          </button>
        </>
      )}
    </div>
  )
}

/** One note: ⠿, body, ✎ and ⋯ 刪除筆記; the form in its place while editing. */
function NoteCard({ note, groupNames, actions }) {
  const [editing, setEditing] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const name = noteName(note)

  return (
    <SortableItem id={note.id} as="li" className="border-b border-border bg-surface px-4 py-3">
      {editing ? (
        <NoteForm
          note={note}
          titleRequired
          groups={groupNames}
          onSave={async (payload) => {
            await actions.patchNote(note.id, payload)
            setEditing(false)
          }}
          onCancel={() => setEditing(false)}
        />
      ) : (
        <div className="flex items-start gap-2">
          <DragHandle label={name} className="pt-0.5" />
          <NoteBody
            note={note}
            onDescription={(description) => actions.patchNote(note.id, { description })}
          />
          <button
            type="button"
            aria-label={`編輯「${name}」`}
            onClick={() => setEditing(true)}
            className="px-1 text-xs text-text-faint hover:text-text"
            style={{ minHeight: 0 }}
          >
            ✎
          </button>
          <DeleteMenu
            label="刪除筆記"
            menuLabel={`「${name}」的選單`}
            onSelect={() => setConfirming(true)}
          />
        </div>
      )}
      {confirming && (
        <ConfirmDialog
          title={`刪除「${name}」？`}
          body="這則筆記和它的連結都會一起刪除。"
          confirmLabel="刪除"
          onConfirm={() => {
            setConfirming(false)
            actions.deleteNote(note.id)
          }}
          onCancel={() => setConfirming(false)}
        />
      )}
    </SortableItem>
  )
}

export default function Notes() {
  const notes = useApiQuery(KEY, endpoints.notes.index())
  const [adding, setAdding] = useState(false)
  const queryClient = useQueryClient()

  const addNote = useApiMutation({
    invalidate: [KEY],
    mutationFn: (payload) => send(endpoints.notes.index(), 'POST', payload),
  })
  const patchNote = useApiMutation({
    invalidate: [KEY],
    mutationFn: ({ id, changes }) => send(endpoints.notes.detail(id), 'PATCH', changes),
  })
  const deleteNote = useApiMutation({
    invalidate: [KEY],
    mutationFn: (id) => send(endpoints.notes.detail(id), 'DELETE'),
  })
  // Optimistic, as the 交通 index is: a dropped note stays where it was dropped
  // during the round trip, and the list is read again either way, so a
  // refusal puts the server's order back.
  const reorder = useApiMutation({
    mutationFn: (noteIds) => send(endpoints.notes.order(), 'PUT', { note_ids: noteIds }),
    onMutate: (noteIds) => {
      queryClient.setQueryData(KEY, (current) => current && reposition(current, noteIds))
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: KEY }),
  })

  if (notes.isLoading) return <LoadingState label="載入筆記中…" />
  if (notes.isError) return <ErrorState error={notes.error} onRetry={notes.refetch} />

  const groups = groupByName(notes.data)
  const named = namedGroups(groups)
  const groupNames = named.map((group) => group.name)
  const actions = {
    // Returns the promise: the form shows a refusal under itself and closes
    // only once the note is saved.
    patchNote: (id, changes) => patchNote.mutateAsync({ id, changes }),
    deleteNote: (id) => deleteNote.mutate(id),
  }

  return (
    <main className="mx-auto max-w-4xl pb-16">
      <div className="flex items-center justify-between gap-2 px-4 pt-6">
        <h1 className="m-0 text-xl font-semibold">筆記</h1>
        {!adding && (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="rounded-md bg-brand px-4 text-sm font-medium text-on-brand"
          >
            + 新增筆記
          </button>
        )}
      </div>
      {adding && (
        <div className="mt-3 px-4">
          <NoteForm
            titleRequired
            groups={groupNames}
            onSave={async (payload) => {
              await addNote.mutateAsync(payload)
              setAdding(false)
            }}
            onCancel={() => setAdding(false)}
          />
        </div>
      )}

      {reorder.isError && (
        <p role="alert" className="m-0 mt-3 px-4 text-sm text-danger">
          排序沒有儲存，已還原。
        </p>
      )}
      {deleteNote.isError && (
        <p role="alert" className="m-0 mt-3 px-4 text-sm text-danger">
          無法刪除筆記，請再試一次。
        </p>
      )}

      {notes.data.length === 0 && !adding ? (
        <EmptyState>還沒有筆記。按「+ 新增筆記」開始。</EmptyState>
      ) : (
        groups.map((group) => {
          const ids = group.items.map((note) => note.id)
          const namedIndex = named.indexOf(group)
          return (
            <section key={group.key} aria-label={group.name ?? undefined} className="mt-3">
              {group.name && (
                <GroupHeading
                  name={group.name}
                  isFirst={namedIndex === 0}
                  isLast={namedIndex === named.length - 1}
                  disabled={reorder.isPending}
                  onMove={
                    named.length > 1
                      ? (delta) =>
                          reorder.mutate(
                            orderAfterGroupSort(groups, moveBy(named, namedIndex, delta)),
                          )
                      : undefined
                  }
                />
              )}
              <ul className="m-0 list-none border-t border-border p-0">
                <SortableList
                  ids={ids}
                  onMove={(from, to) =>
                    reorder.mutate(orderIds(moveInGroup(groups, group.key, from, to)))
                  }
                >
                  {group.items.map((note) => (
                    <NoteCard key={note.id} note={note} groupNames={groupNames} actions={actions} />
                  ))}
                </SortableList>
              </ul>
            </section>
          )
        })
      )}
    </main>
  )
}
