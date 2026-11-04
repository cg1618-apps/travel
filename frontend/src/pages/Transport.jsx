/**
 * 交通: every route, one card each.
 *
 * Compact on purpose, the way 行程 is: 起點 → 終點 and one line per way of
 * making the journey, enough to tell routes apart. Everything else - every
 * field, the links, the departures and the next one from now - is one click
 * away on /transport/:id (`TransportRoute.jsx`). The ⠿ beside each card
 * drags it into a new order, which the server keeps.
 */

import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { endpoints } from '../api/endpoints'
import { DragHandle, SortableItem, SortableList } from '../components/Sortable'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { send, useApiMutation, useApiQuery } from '../hooks/useApiQuery'
import { keysFor } from '../lib/keys'
import { inIdOrder, moveTo, optionSummary } from '../lib/transport'
import { firstLine } from '../lib/trips'

const KEY = ['transport-routes']
const INDEX = [...KEY, 'index']

const inputClass = 'rounded-md border border-border bg-canvas px-2 py-1.5 text-sm text-text min-w-0'
const smallButton = 'rounded-md border border-border-strong px-3 text-sm text-text-muted'

/**
 * 起點, 終點 and 建立. Creating opens the new route. `pending` holds 建立
 * while a create is in flight, so a second click cannot make a second route.
 */
function CreateRoute({ pending, failed, onCreate, onCancel }) {
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const ready = from.trim() !== '' && to.trim() !== ''

  const submit = () => {
    if (!ready || pending) return
    onCreate({ from_place: from.trim(), to_place: to.trim() })
  }
  const onKeyDown = keysFor(submit, onCancel)

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 px-4">
      <input
        autoFocus
        value={from}
        aria-label="起點"
        placeholder="起點"
        onChange={(event) => setFrom(event.target.value)}
        onKeyDown={onKeyDown}
        className={`${inputClass} w-36`}
      />
      <span className="text-text-faint">→</span>
      <input
        value={to}
        aria-label="終點"
        placeholder="終點"
        onChange={(event) => setTo(event.target.value)}
        onKeyDown={onKeyDown}
        className={`${inputClass} w-36`}
      />
      <button
        type="button"
        disabled={!ready || pending}
        onClick={submit}
        className={`${smallButton} disabled:opacity-40`}
      >
        建立
      </button>
      <button type="button" onClick={onCancel} className={smallButton}>
        取消
      </button>
      {failed && (
        <p role="alert" className="m-0 w-full text-sm text-danger">
          無法建立路線，請再試一次。
        </p>
      )}
    </div>
  )
}

/**
 * One route: 起點 → 終點, the first line of 備註, one line per 交通方式. The
 * grip sits outside the link, so picking a card up never opens it.
 */
function RouteCard({ route }) {
  const note = firstLine(route.notes)
  const name = `${route.from_place} → ${route.to_place}`
  return (
    <SortableItem id={route.id} as="li" className="flex items-start border-b border-border">
      <DragHandle label={name} className="py-3 pl-3 pr-1" />
      <Link
        to={`/transport/${route.id}`}
        className="block min-w-0 flex-1 py-3 pl-1 pr-4 text-text no-underline"
      >
        <span className="block font-semibold">{name}</span>
        {note && <span className="block text-xs text-text-faint">{note}</span>}
        {route.options.length === 0 ? (
          <span className="block text-sm text-text-faint">沒有交通方式</span>
        ) : (
          route.options.map((option) => (
            <span key={option.id} className="block text-sm tabular-nums text-text-muted">
              {optionSummary(option)}
            </span>
          ))
        )}
      </Link>
    </SortableItem>
  )
}

export default function Transport() {
  const navigate = useNavigate()
  const routes = useApiQuery(INDEX, endpoints.transport.routes())
  const [creating, setCreating] = useState(false)

  const create = useApiMutation({
    invalidate: [KEY],
    mutationFn: (payload) => send(endpoints.transport.routes(), 'POST', payload),
    onSuccess: (created) => navigate(`/transport/${created.id}`),
  })
  // Optimistic, as a packing list's rows are: a dropped card stays where it was
  // dropped during the round trip, the response replaces the cache, and a
  // refusal puts the server's order back.
  const queryClient = useQueryClient()
  const reorder = useApiMutation({
    mutationFn: (routeIds) =>
      send(endpoints.transport.routesOrder(), 'PUT', { route_ids: routeIds }),
    onMutate: (routeIds) => {
      queryClient.setQueryData(INDEX, (current) => current && inIdOrder(current, routeIds))
    },
    onSuccess: (updated) => queryClient.setQueryData(INDEX, updated),
    onError: () => queryClient.invalidateQueries({ queryKey: INDEX }),
  })

  if (routes.isLoading) return <LoadingState label="載入路線中…" />
  if (routes.isError) return <ErrorState error={routes.error} onRetry={routes.refetch} />

  const ids = routes.data.map((route) => route.id)

  return (
    <main className="mx-auto max-w-4xl pb-16">
      <div className="flex items-center justify-between px-4 pt-6">
        <h1 className="m-0 text-xl font-semibold">交通</h1>
        {!creating && (
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="rounded-md bg-brand px-4 text-sm font-medium text-on-brand"
          >
            + 新增路線
          </button>
        )}
      </div>
      {creating && (
        <CreateRoute
          pending={create.isPending}
          failed={create.isError}
          onCreate={create.mutate}
          onCancel={() => setCreating(false)}
        />
      )}

      {routes.data.length === 0 ? (
        <EmptyState>還沒有路線。按「+ 新增路線」開始。</EmptyState>
      ) : (
        <>
          {reorder.isError && (
            <p role="alert" className="m-0 mt-3 px-4 text-sm text-danger">
              排序沒有儲存，已還原。
            </p>
          )}
          <ul className="m-0 mt-3 list-none border-t border-border p-0">
            <SortableList ids={ids} onMove={(from, to) => reorder.mutate(moveTo(ids, from, to))}>
              {routes.data.map((route) => (
                <RouteCard key={route.id} route={route} />
              ))}
            </SortableList>
          </ul>
        </>
      )}
    </main>
  )
}
