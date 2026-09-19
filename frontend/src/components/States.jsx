/**
 * Loading, error and empty, defined once.
 *
 * Media keeps these as shared components rather than reimplementing them per
 * page, which is what stops three screens disagreeing about what "nothing
 * here" looks like.
 */

export function LoadingState({ label = 'Loading…' }) {
  return (
    <div className="px-4 py-12 text-center text-text-faint" role="status">
      {label}
    </div>
  )
}

export function ErrorState({ error, onRetry }) {
  return (
    <div
      className="mx-4 my-6 rounded-md border border-danger/40 bg-danger/10 px-4 py-3 text-text"
      role="alert"
    >
      <p className="m-0 text-sm">{error?.message || 'Something went wrong.'}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 rounded-md border border-border-strong px-3 text-sm"
        >
          Try again
        </button>
      )}
    </div>
  )
}

/** An empty state offers the action that fills it, rather than just saying no. */
export function EmptyState({ children, action }) {
  return (
    <div className="px-4 py-10 text-center">
      <p className="m-0 text-text-muted">{children}</p>
      {action && <div className="mt-3">{action}</div>}
    </div>
  )
}
