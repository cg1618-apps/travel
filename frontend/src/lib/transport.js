/**
 * Transport display logic that is not a component: prices, and a route's
 * departures split by day type.
 */

export const DAY_TYPES = ['weekday', 'holiday']

/** 22 → "NT$22"; null stays null so the cell can show its placeholder. */
export function formatPrice(price) {
  return price === null || price === undefined ? null : `NT$${price}`
}

/**
 * What typing in the price cell means: '' clears it, a whole number sets it,
 * anything else is refused (undefined) so a typo never reaches the API.
 */
export function parsePrice(text) {
  const trimmed = text.trim()
  if (trimmed === '') return null
  if (!/^\d+$/.test(trimmed)) return undefined
  return Number(trimmed)
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
