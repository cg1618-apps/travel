/**
 * The single place that talks to fetch().
 *
 * Everything else goes through endpoints.js for URLs and the query hooks for
 * state. Copied in shape from the media tracker's client so an error reads the
 * same way in both apps.
 */

async function parse(response) {
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

export async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  const data = await parse(response)

  if (!response.ok) {
    // `detail` is a plain string on every endpoint - see docs/api.md. A 422
    // from a schema is the one exception: FastAPI returns a list there, so it
    // is flattened rather than rendered as [object Object].
    const detail = data?.detail
    const message = Array.isArray(detail)
      ? detail.map((part) => part.msg).join('; ')
      : detail || `Request failed (${response.status})`
    throw new ApiError(message, response.status, data)
  }
  return data
}

export const jsonBody = (body) => ({ body: JSON.stringify(body) })
