/**
 * The front page: 一般 lists and trips that are 使用中 or 未來使用, 使用中 first.
 * Nothing to add or edit.
 */

import { Link } from 'react-router-dom'

import { endpoints } from '../api/endpoints'
import { ErrorState, LoadingState } from '../components/States'
import { useApiQuery } from '../hooks/useApiQuery'
import { onDashboard } from '../lib/kinds'
import { LEG_LABELS, USAGE_LABELS } from '../lib/labels'
import { departureLabel } from '../lib/timing'
import { tripDateRange } from '../lib/trips'

function Section({ title, more, children }) {
  return (
    <section className="mt-8">
      <div className="mx-4 mb-2 flex items-baseline justify-between">
        <h2 className="m-0 text-xs font-semibold uppercase tracking-wide text-text-faint">
          {title}
        </h2>
        <Link to={more.to} className="text-sm text-brand">
          {more.label}
        </Link>
      </div>
      {children}
    </section>
  )
}

function Empty({ children }) {
  return <p className="px-4 py-6 text-center text-sm text-text-muted">{children}</p>
}

function Badge({ children }) {
  return (
    <span className="ml-2 rounded-sm bg-surface-2 px-1.5 py-0.5 text-xs text-text-muted">
      {children}
    </span>
  )
}

function Lists({ rows }) {
  if (rows.length === 0) {
    return <Empty>目前沒有使用中或未來使用的清單。</Empty>
  }
  const today = new Date()
  return (
    <ul className="m-0 list-none border-t border-border p-0">
      {rows.map((row) => (
        <li key={row.id} className="border-b border-border bg-surface">
          <Link
            to={`/lists/${row.id}`}
            className="flex items-baseline justify-between gap-3 px-4 py-3 text-text no-underline"
          >
            <span className="min-w-0">
              {row.name}
              {row.leg && <span className="ml-2 text-xs text-text-faint">{LEG_LABELS[row.leg]}</span>}
              <Badge>{USAGE_LABELS[row.usage]}</Badge>
            </span>
            <span className="shrink-0 text-sm tabular-nums text-text-muted">
              {departureLabel(row.departure_at, today)} · 已處理 {row.settled_count} /{' '}
              {row.item_count}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  )
}

function Trips({ trips }) {
  if (trips.length === 0) {
    return <Empty>目前沒有使用中或未來使用的行程。</Empty>
  }
  return (
    <ul className="m-0 list-none border-t border-border p-0">
      {trips.map((trip) => (
        <li key={trip.id} className="border-b border-border bg-surface">
          <Link
            to={`/trips/${trip.id}`}
            className="flex items-baseline justify-between gap-3 px-4 py-3 text-text no-underline"
          >
            <span className="min-w-0">
              {trip.name}
              <Badge>{USAGE_LABELS[trip.usage]}</Badge>
            </span>
            <span className="shrink-0 text-sm tabular-nums text-text-muted">
              {tripDateRange(trip.legs) ?? '沒有行程段'}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  )
}

export default function Dashboard() {
  const lists = useApiQuery(['packing-lists'], endpoints.packingLists.index())
  const trips = useApiQuery(['trips', 'index'], endpoints.trips.index())

  if (lists.isLoading || trips.isLoading) return <LoadingState />
  for (const query of [lists, trips]) {
    if (query.isError) return <ErrorState error={query.error} onRetry={query.refetch} />
  }

  return (
    <main className="mx-auto max-w-4xl pb-16 pt-6">
      <h1 className="m-0 px-4 text-xl font-semibold">travel</h1>
      <Section title="清單" more={{ to: '/lists', label: '所有清單' }}>
        <Lists rows={onDashboard(lists.data.free)} />
      </Section>
      <Section title="行程" more={{ to: '/trips', label: '所有行程' }}>
        <Trips trips={onDashboard(trips.data.free)} />
      </Section>
    </main>
  )
}
