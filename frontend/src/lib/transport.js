/**
 * Transport display logic that is not a component: how a price is shown, and
 * a route's departures split by day type. Typing a price is `parseWholeNumber`
 * in `numbers.js`.
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
