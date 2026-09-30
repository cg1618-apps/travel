/**
 * A yes/no question put before an action that cannot be taken back.
 *
 * `EvictDialog`'s markup with generic props: a bottom sheet on a phone, a
 * centred card on a wide screen, the action first and cancel beneath it.
 */

export function ConfirmDialog({ title, body, confirmLabel, onConfirm, onCancel }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-ink/50 p-0 sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
    >
      <div className="w-full max-w-md rounded-t-2xl border border-border bg-surface p-5 sm:rounded-2xl">
        <h2 id="confirm-title" className="m-0 text-base font-semibold">
          {title}
        </h2>
        <p className="mt-2 text-sm text-text-muted">{body}</p>

        <div className="mt-5 flex flex-col gap-2">
          <button
            type="button"
            onClick={onConfirm}
            className="rounded-md bg-brand px-4 font-medium text-on-brand"
          >
            {confirmLabel}
          </button>
          <button type="button" onClick={onCancel} className="px-4 text-text-muted">
            取消
          </button>
        </div>
      </div>
    </div>
  )
}
