/**
 * TanStack Query over `fetchJson`.
 *
 * Every screen in this app is editable, and media's split is react-query for
 * anything written back from the UI, plain fetch for read-only pages. So all
 * of them come through here.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { fetchJson, jsonBody } from '../api/client'

export function useApiQuery(key, url, options = {}) {
  return useQuery({ queryKey: key, queryFn: () => fetchJson(url), ...options })
}

/**
 * A mutation that invalidates what it touched.
 *
 * `invalidate` is a list of query keys rather than a refetch of everything:
 * checking an item off has to feel instant on a phone, and re-reading the
 * whole index on every tap is what makes it not.
 */
export function useApiMutation({ invalidate = [], onError, ...rest }) {
  const queryClient = useQueryClient()
  return useMutation({
    ...rest,
    onSuccess: (...args) => {
      invalidate.forEach((key) => queryClient.invalidateQueries({ queryKey: key }))
      rest.onSuccess?.(...args)
    },
    onError,
  })
}

export const send = (url, method, body) =>
  fetchJson(url, { method, ...(body === undefined ? {} : jsonBody(body)) })
