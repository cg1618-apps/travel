/**
 * On a 範本's own page: make a new list or trip from it, without going back to
 * the index. A button, then a small form with the name already filled in from
 * the template. `dateRequired` is a trip whose entries have times to move.
 */

import { useState } from 'react'

import { keysFor } from '../lib/keys'
import { autofillName } from '../lib/kinds'

const inputClass = 'rounded-md border border-border bg-canvas px-2 py-1.5 text-sm text-text min-w-0'
const smallButton = 'rounded-md border border-border-strong px-3 text-sm text-text-muted'

export function CreateFromTemplate({
  template,
  noun,
  dateRequired = false,
  pending = false,
  failed = false,
  onCreate,
}) {
  const [open, setOpen] = useState(false)
  const initialName = autofillName({ current: '', lastFill: '', source: template.name }).name
  const [name, setName] = useState(initialName)
  const [date, setDate] = useState('')
  const ready = Boolean(name.trim()) && (!dateRequired || Boolean(date))

  const close = () => {
    setOpen(false)
    setName(initialName)
    setDate('')
  }
  const submit = () => {
    if (ready && !pending) onCreate({ name: name.trim(), date: date || null })
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="rounded-md bg-brand px-4 text-sm font-medium text-on-brand"
      >
        + 從這份範本建立{noun}
      </button>
    )
  }
  return (
    <div className="flex w-full flex-wrap items-center gap-2">
      <input
        autoFocus
        aria-label={`新${noun}名稱`}
        placeholder={`${noun}名稱`}
        value={name}
        onFocus={(event) => event.target.select()}
        onChange={(event) => setName(event.target.value)}
        onKeyDown={keysFor(submit, close)}
        className={`${inputClass} w-48`}
      />
      <input
        type="date"
        aria-label={dateRequired ? '出發日期（必填）' : '出發日期'}
        value={date}
        onChange={(event) => setDate(event.target.value)}
        className={inputClass}
      />
      <button
        type="button"
        disabled={!ready || pending}
        onClick={submit}
        className={`${smallButton} disabled:opacity-40`}
      >
        建立
      </button>
      <button type="button" onClick={close} className={smallButton}>
        取消
      </button>
      {dateRequired && !date && <p className="m-0 w-full text-xs text-text-faint">需要出發日期。</p>}
      {failed && (
        <p role="alert" className="m-0 w-full text-sm text-danger">
          無法建立{noun}，請再試一次。
        </p>
      )}
    </div>
  )
}
