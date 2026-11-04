/**
 * 筆記, shared by a 交通 route and the 筆記 page: the form a note is added and
 * edited in, and how a note reads.
 *
 * A list of links is not a cell, so a note is edited in a small form of its
 * own with 儲存 and 取消. Its links are reordered there with ↑ / ↓; the order
 * saved is the order the form shows. A route's note needs a title or a link;
 * the 筆記 page's needs a title (`titleRequired`) and has a 群組 field
 * (`groups`, the names already in use, offered as suggestions).
 */

import { useState } from 'react'

import { canSaveNote, linkText, moveBy, noteName, notePayload } from '../lib/transport'
import { TextAreaCell } from './Cell'
import { Combobox } from './Combobox'

const inputClass = 'rounded-md border border-border bg-canvas px-2 py-1.5 text-sm text-text min-w-0'
const smallButton = 'rounded-md border border-border-strong px-3 text-sm text-text-muted'
const iconButton = 'px-2 text-text-faint hover:text-text disabled:opacity-30'

export function NoteForm({ note, onSave, onCancel, titleRequired = false, groups = null }) {
  const [title, setTitle] = useState(note?.title ?? '')
  const [description, setDescription] = useState(note?.description ?? '')
  const [group, setGroup] = useState(note?.group_name ?? '')
  // Keyed by a counter rather than by place, so removing or moving one input
  // does not hand its neighbour's text to the wrong field.
  const [links, setLinks] = useState(() =>
    (note?.links.length ? note.links : ['']).map((url, key) => ({ key, url })),
  )
  const [nextKey, setNextKey] = useState(links.length)
  const [pending, setPending] = useState(false)
  const [problem, setProblem] = useState(null)
  const fields = { title, description, links: links.map((link) => link.url) }
  if (groups) fields.group_name = group
  const saveable = canSaveNote(fields, { titleRequired })

  const setLink = (key, url) =>
    setLinks(links.map((link) => (link.key === key ? { key, url } : link)))
  const addLink = () => {
    setLinks([...links, { key: nextKey, url: '' }])
    setNextKey(nextKey + 1)
  }

  const submit = async () => {
    if (!saveable || pending) return
    setPending(true)
    try {
      await onSave(notePayload(fields))
    } catch {
      setProblem('無法儲存筆記，請再試一次。')
      setPending(false)
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-md border border-dashed border-border-strong p-3">
      <input
        autoFocus
        aria-label="筆記標題"
        placeholder={titleRequired ? '標題（必填）' : '標題'}
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        className={`${inputClass} w-full`}
      />
      {groups && (
        <Combobox
          aria-label="群組"
          placeholder="群組（可不填）"
          value={group}
          onChange={setGroup}
          options={groups}
          className={`${inputClass} w-full sm:w-60`}
        />
      )}
      <textarea
        aria-label="筆記說明"
        placeholder="說明"
        rows={3}
        value={description}
        onChange={(event) => setDescription(event.target.value)}
        className={`${inputClass} w-full`}
      />
      {links.map((link, index) => (
        <div key={link.key} className="flex items-center gap-1">
          <input
            type="url"
            aria-label={`連結 ${index + 1}`}
            placeholder="https://"
            value={link.url}
            onChange={(event) => setLink(link.key, event.target.value)}
            className={`${inputClass} min-w-0 flex-1`}
          />
          <button
            type="button"
            aria-label={`連結 ${index + 1} 上移`}
            disabled={index === 0}
            onClick={() => setLinks(moveBy(links, index, -1))}
            className={iconButton}
            style={{ minHeight: 0 }}
          >
            ↑
          </button>
          <button
            type="button"
            aria-label={`連結 ${index + 1} 下移`}
            disabled={index === links.length - 1}
            onClick={() => setLinks(moveBy(links, index, 1))}
            className={iconButton}
            style={{ minHeight: 0 }}
          >
            ↓
          </button>
          <button
            type="button"
            aria-label={`移除連結 ${index + 1}`}
            onClick={() => setLinks(links.filter((other) => other.key !== link.key))}
            className={iconButton}
            style={{ minHeight: 0 }}
          >
            ✕
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={addLink}
        className="self-start text-sm text-brand"
        style={{ minHeight: 0 }}
      >
        + 新增連結
      </button>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={!saveable || pending}
          onClick={submit}
          className={`${smallButton} disabled:opacity-40`}
        >
          儲存
        </button>
        <button type="button" onClick={onCancel} className={smallButton}>
          取消
        </button>
      </div>
      {!saveable && (
        <p className="m-0 text-xs text-text-faint">
          {titleRequired ? '需要標題。' : '需要標題或至少一個連結。'}
        </p>
      )}
      {problem && (
        <p role="alert" className="m-0 text-xs text-danger">
          {problem}
        </p>
      )}
    </div>
  )
}

/**
 * One note as read: title, description with its line breaks, then its links.
 * With `onDescription` the description is a `TextAreaCell`, edited in place.
 */
export function NoteBody({ note, onDescription }) {
  return (
    <div className="min-w-0 flex-1">
      {note.title && <p className="m-0 font-semibold">{note.title}</p>}
      {onDescription ? (
        <div className="-mx-2 text-text-muted">
          <TextAreaCell
            value={note.description}
            placeholder="說明"
            ariaLabel={`「${noteName(note)}」的說明`}
            onCommit={onDescription}
          />
        </div>
      ) : (
        note.description && (
          <p className="m-0 whitespace-pre-wrap break-words text-sm text-text-muted">
            {note.description}
          </p>
        )
      )}
      {note.links.map((url, index) => (
        <a
          // A link may appear twice in one note; its place keeps the key unique.
          key={`${index}-${url}`}
          href={url}
          target="_blank"
          rel="noreferrer"
          title={url}
          className="block truncate text-sm text-brand"
        >
          {linkText(url)}
        </a>
      ))}
    </div>
  )
}
