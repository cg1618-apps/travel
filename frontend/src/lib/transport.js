/**
 * Transport logic that is not a component: how a price is shown, a route's
 * departures split by day type, the order a drag leaves routes and options
 * in, and a 筆記's fields as the API takes them. Typing a price is
 * `parseWholeNumber` in `numbers.js`.
 */

export const DAY_TYPES = ['weekday', 'holiday']

/** 22 → "NT$22"; null stays null so the cell can show its placeholder. */
export function formatPrice(price) {
  return price === null || price === undefined ? null : `NT$${price}`
}

/**
 * The API reads departures holiday-first (alphabetical day_type); the sheet
 * puts 平日 first, so the page groups for itself and does not lean on order.
 */
export function groupByDayType(departures) {
  const groups = Object.fromEntries(DAY_TYPES.map((type) => [type, []]))
  for (const departure of departures) groups[departure.day_type]?.push(departure)
  return groups
}

/**
 * One way of making a route, on one line of the 交通 index: 交通方式, then
 * 價錢 and 時間 when set — "公車 307 · NT$15 · 40分".
 */
export function optionSummary({ mode, price, duration }) {
  return [mode, formatPrice(price), duration].filter(Boolean).join(' · ')
}

/** `list` with the entry at `from` moved to `to` — one drop or one ↑ / ↓. */
export function moveTo(list, from, to) {
  const next = [...list]
  const [moved] = next.splice(from, 1)
  next.splice(to, 0, moved)
  return next
}

/**
 * `rows` in the order `ids` names — a reorder applied to the cache before the
 * server answers. A row `ids` does not name keeps its place at the end.
 */
export function inIdOrder(rows, ids) {
  const rank = (row) => {
    const index = ids.indexOf(row.id)
    return index === -1 ? ids.length : index
  }
  return [...rows].sort((a, b) => rank(a) - rank(b))
}

/**
 * A 筆記 form's fields as the API takes them: blanks as null, and empty link
 * inputs dropped, because the API refuses a blank link.
 */
export function notePayload({ title, description, links }) {
  return {
    title: title.trim() || null,
    description: description.trim() || null,
    links: links.map((link) => link.trim()).filter(Boolean),
  }
}

/** A note needs a title or a link; a description alone is not enough. */
export function canSaveNote(fields) {
  const { title, links } = notePayload(fields)
  return title !== null || links.length > 0
}

/**
 * A note link as shown: host and path, without the scheme or a trailing
 * slash, so it reads on a phone. Anything that is not a URL is shown as typed.
 */
export function linkText(url) {
  try {
    const parsed = new URL(url)
    return `${parsed.host}${parsed.pathname}`.replace(/\/$/, '')
  } catch {
    return url
  }
}
