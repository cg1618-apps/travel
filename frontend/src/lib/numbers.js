/**
 * Typing a count into a cell: 價錢, and 數量 on a packing item.
 *
 * '' clears the value (null), a whole number sets it, and anything else is
 * refused (undefined) so a typo such as "1.5" never reaches the API, which
 * would reject it with a 422 the cell has no way to show.
 */
export function parseWholeNumber(text) {
  const trimmed = text.trim()
  if (trimmed === '') return null
  if (!/^\d+$/.test(trimmed)) return undefined
  return Number(trimmed)
}
