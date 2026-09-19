/**
 * What stands between a new list and a destroyed one.
 *
 * The 409 is not an error toast. It is a decision, and the safe option is
 * listed first and styled as the primary one: a destructive confirm whose
 * safe option is missing, or buried, gets clicked through.
 */

export function EvictDialog({ message, evicting, onSaveInstead, onConfirm, onCancel }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-ink/50 p-0 sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="evict-title"
    >
      <div className="w-full max-w-md rounded-t-2xl border border-border bg-surface p-5 sm:rounded-2xl">
        <h2 id="evict-title" className="m-0 text-base font-semibold">
          This will delete a list
        </h2>
        <p className="mt-2 text-sm text-text-muted">{message}</p>

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
              Save it instead, then continue
            </button>
          )}
          <button
            type="button"
            onClick={onConfirm}
            className="rounded-md border border-danger px-4 text-danger"
          >
            Delete it and continue
          </button>
          <button type="button" onClick={onCancel} className="px-4 text-text-muted">
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
