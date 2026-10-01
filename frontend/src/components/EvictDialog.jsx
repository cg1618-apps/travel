/**
 * What stands between 過去使用 and a dropped list or trip.
 *
 * The 409 is not an error toast. It is a decision, and the safe option is
 * listed first and styled as the primary one: a destructive confirm whose
 * safe option is missing, or buried, gets clicked through.
 *
 * The body is this dialog's own words, not the refusal's `detail`: that is the
 * API's English contract, and the names it carries arrive as `evicting` from
 * `evict_next` on the index anyway.
 */

export function EvictDialog({
  body,
  noun = '一份清單',
  confirmLabel = '刪除並繼續',
  evicting,
  onSaveInstead,
  onConfirm,
  onCancel,
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-ink/50 p-0 sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="evict-title"
    >
      <div className="w-full max-w-md rounded-t-2xl border border-border bg-surface p-5 sm:rounded-2xl">
        <h2 id="evict-title" className="m-0 text-base font-semibold">
          這會刪除{noun}
        </h2>
        <p className="mt-2 text-sm text-text-muted">{body}</p>

        {evicting?.length > 0 && (
          <ul className="mt-3 list-none space-y-1 rounded-md bg-surface-2 p-3 text-sm">
            {evicting.map((row) => (
              <li key={row.id}>{row.name}</li>
            ))}
          </ul>
        )}

        <div className="mt-5 flex flex-col gap-2">
          {onSaveInstead && (
            <button
              type="button"
              onClick={onSaveInstead}
              className="rounded-md bg-brand px-4 font-medium text-on-brand"
            >
              改為保存它
            </button>
          )}
          <button
            type="button"
            onClick={onConfirm}
            className="rounded-md border border-danger px-4 text-danger"
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
