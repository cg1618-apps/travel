/**
 * 狀態, 保存 and 當作範本 for one list or trip, wherever it is shown.
 *
 * 取消保存 asks first, because it puts the row back among the 一般 ones as
 * 未使用 - the dialog lives here so every place that shows the checkbox asks
 * the same question.
 */

import { useState } from 'react'

import { USAGES, USAGE_LABELS } from '../lib/labels'
import { ConfirmDialog } from './ConfirmDialog'

export function KindControls({ row, noun, onPatch, onMakeTemplate }) {
  const [confirmingUnsave, setConfirmingUnsave] = useState(false)
  if (row.kind === 'template') return null
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      {row.kind === 'free' && (
        <select
          aria-label={`「${row.name}」的狀態`}
          value={row.usage}
          onChange={(event) => onPatch({ usage: event.target.value })}
          className="rounded-md border border-border bg-canvas px-2 py-1 text-sm text-text"
        >
          {USAGES.map((usage) => (
            <option key={usage} value={usage}>
              {USAGE_LABELS[usage]}
            </option>
          ))}
        </select>
      )}
      <label className="flex items-center gap-1 text-text-muted">
        <input
          type="checkbox"
          checked={row.kind === 'saved'}
          onChange={(event) =>
            event.target.checked ? onPatch({ kind: 'saved' }) : setConfirmingUnsave(true)
          }
          className="size-4"
        />
        保存
      </label>
      <button
        type="button"
        onClick={onMakeTemplate}
        className="rounded-md border border-border-strong px-3 text-sm text-text-muted"
        style={{ minHeight: 32 }}
      >
        當作範本
      </button>
      {confirmingUnsave && (
        <ConfirmDialog
          title={`取消保存「${row.name}」？`}
          body={`取消保存後會回到一般${noun}（未使用）。`}
          confirmLabel="取消保存"
          onConfirm={() => {
            setConfirmingUnsave(false)
            onPatch({ kind: 'free' })
          }}
          onCancel={() => setConfirmingUnsave(false)}
        />
      )}
    </div>
  )
}
