/**
 * Loading, error and empty, defined once.
 *
 * Media keeps these as shared components rather than reimplementing them per
 * page, which is what stops three screens disagreeing about what "nothing
 * here" looks like.
 */

import { useEffect } from 'react'

export function LoadingState({ label = '載入中…' }) {
  return (
    <div className="px-4 py-12 text-center text-text-faint" role="status">
      {label}
    </div>
  )
}

/**
 * The message is this app's own, not the error's: an API `detail` is English
 * by contract and a network failure is the browser's wording. The status code
 * is kept, because it is the one part worth reading back to someone. An error
 * with no status never reached the server, so it says so rather than blaming
 * the server; the error itself goes to the console, where it can be read.
 */
export function ErrorState({ error, onRetry }) {
  useEffect(() => {
    if (error) console.error(error)
  }, [error])

  return (
    <div
      className="mx-4 my-6 rounded-md border border-danger/40 bg-danger/10 px-4 py-3 text-text"
      role="alert"
    >
      <p className="m-0 text-sm">
        {error?.status ? (
          <>
            發生錯誤。<span className="text-text-faint">（{error.status}）</span>
          </>
        ) : (
          '無法連線，請稍後再試。'
        )}
      </p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 rounded-md border border-border-strong px-3 text-sm"
        >
          再試一次
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
