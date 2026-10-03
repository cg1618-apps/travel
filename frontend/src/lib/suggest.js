/**
 * What a suggesting input offers for what has been typed so far.
 *
 * Nothing typed offers everything. Otherwise every option containing the
 * text, case-insensitively, with those that start with it first — and the
 * option that already equals the text is left out, since picking it would
 * change nothing.
 */
export function suggest(options, text) {
  const typed = (text ?? '').trim().toLowerCase()
  if (!typed) return options
  const starts = []
  const contains = []
  for (const option of options) {
    const lower = option.toLowerCase()
    if (lower === typed) continue
    if (lower.startsWith(typed)) starts.push(option)
    else if (lower.includes(typed)) contains.push(option)
  }
  return [...starts, ...contains]
}
