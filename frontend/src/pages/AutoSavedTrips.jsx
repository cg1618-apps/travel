/**
 * 自動保存的行程: every 一般 trip set to 過去使用, newest first.
 *
 * 刪除模式 is here because this is where old trips pile up: ticking several
 * and deleting them at once beats ⋯ → 刪除行程 on each. One confirmation names
 * every trip it will delete. Reached from the 行程 page, not the nav bar.
 */

import { useState } from 'react'
import { Link } from 'react-router-dom'

import { endpoints } from '../api/endpoints'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { send, useApiMutation, useApiQuery } from '../hooks/useApiQuery'
import { AUTO_SAVE_LIMIT } from '../lib/kinds'
import { firstLine, tripDateRange } from '../lib/trips'

const smallButton = 'rounded-md border border-border-strong px-3 text-sm text-text-muted'

export default function AutoSavedTrips() {
  const index = useApiQuery(['trips', 'index'], endpoints.trips.index())
  const [deleting, setDeleting] = useState(false)
  const [selected, setSelected] = useState(() => new Set())
  const [confirming, setConfirming] = useState(false)
  // A deleted trip's linked list loses its leg, and with it the date the leg
  // gave it, so the packing-list queries refresh too.
  const remove = useApiMutation({
    invalidate: [['trips'], ['packing-lists'], ['packing-list']],
    mutationFn: (ids) => send(endpoints.trips.bulkDelete(), 'POST', { ids }),
    onSuccess: () => {
      setSelected(new Set())
      setDeleting(false)
    },
  })

  if (index.isLoading) return <LoadingState label="載入行程中…" />
  if (index.isError) return <ErrorState error={index.error} onRetry={index.refetch} />

  const trips = index.data.auto_saved
  const toggle = (id) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelected(next)
  }
  const chosen = trips.filter((trip) => selected.has(trip.id))

  return (
    <main className="mx-auto max-w-4xl px-4 pb-16 pt-6">
      <Link to="/trip" className="text-sm text-text-faint no-underline">
        ← 行程
      </Link>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <h1 className="m-0 text-xl font-semibold">
          自動保存的行程
          <span className="ml-2 text-sm font-normal text-text-faint">
            {trips.length} / {AUTO_SAVE_LIMIT.trips}
          </span>
        </h1>
        {trips.length > 0 && (
          <button
            type="button"
            className={smallButton}
            onClick={() => {
              setDeleting(!deleting)
              setSelected(new Set())
            }}
          >
            {deleting ? '完成' : '刪除模式'}
          </button>
        )}
      </div>

      {trips.length === 0 ? (
        <EmptyState>把一般行程的狀態設為「過去使用」，它會自動保存在這裡。</EmptyState>
      ) : (
        <>
          {deleting && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <label className="flex items-center gap-1 text-sm text-text-muted">
                <input
                  type="checkbox"
                  className="size-4"
                  checked={chosen.length === trips.length}
                  onChange={(event) =>
                    setSelected(
                      event.target.checked ? new Set(trips.map((trip) => trip.id)) : new Set(),
                    )
                  }
                />
                全選
              </label>
              <button
                type="button"
                disabled={chosen.length === 0 || remove.isPending}
                onClick={() => setConfirming(true)}
                className="rounded-md border border-danger px-3 text-sm text-danger disabled:opacity-40"
              >
                刪除所選（{chosen.length}）
              </button>
            </div>
          )}
          {remove.isError && (
            <p role="alert" className="m-0 mt-2 text-sm text-danger">
              無法刪除，請再試一次。
            </p>
          )}
          <ul className="m-0 mt-3 list-none border-t border-border p-0">
            {trips.map((trip) => (
              <li key={trip.id} className="flex items-center gap-3 border-b border-border py-2">
                {deleting && (
                  <input
                    type="checkbox"
                    className="size-4"
                    aria-label={`選取「${trip.name}」`}
                    checked={selected.has(trip.id)}
                    onChange={() => toggle(trip.id)}
                  />
                )}
                <Link
                  to={`/trips/${trip.id}`}
                  className="flex min-w-0 flex-1 justify-between gap-3 text-brand"
                >
                  <span className="min-w-0">
                    {trip.name}
                    {trip.archive_note && (
                      <span className="ml-2 text-sm text-text-faint">
                        {firstLine(trip.archive_note)}
                      </span>
                    )}
                  </span>
                  <span className="shrink-0 tabular-nums text-text-faint">
                    {tripDateRange(trip.legs) ?? '沒有行程段'}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}

      {confirming && (
        <ConfirmDialog
          title={`刪除 ${chosen.length} 個行程？`}
          body={`${chosen.map((trip) => `「${trip.name}」`).join('、')}和它們所有的行程段都會一起刪除，連結的打包清單不受影響。`}
          confirmLabel="刪除"
          onConfirm={() => {
            setConfirming(false)
            remove.mutate(chosen.map((trip) => trip.id))
          }}
          onCancel={() => setConfirming(false)}
        />
      )}
    </main>
  )
}
