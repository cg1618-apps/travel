/**
 * Which tone (see `index.css`) a value is shown in.
 *
 * The closed vocabularies are spelled out, so a colour means the same thing
 * every time: green is done, amber is waiting on you, and 打包時機 warms as it
 * gets closer to leaving. 取得地點 is open text, so its tone is derived from
 * the text itself — the same place is always the same colour, on every list.
 * `null` means no tone: the value is shown plain.
 */

export const STATUS_TONES = { not_packed: 'gray', packed: 'green', no_need: null }
export const CHECK_TONES = { off: null, needed: 'amber', done: 'green' }
export const TIMING_TONES = {
  whenever: 'gray',
  night_before: 'violet',
  day_of: 'orange',
  just_before: 'rose',
}
export const NEED_TONES = { need: 'sky', bring: 'teal', buy: 'pink' }

const OPEN_TONES = ['sky', 'violet', 'teal', 'orange', 'lime', 'pink', 'amber', 'rose']

/** A stable tone for a free-text value; null for a blank one. */
export function toneForText(text) {
  if (!text) return null
  let hash = 0
  for (const char of text) hash = (hash * 31 + char.codePointAt(0)) >>> 0
  return OPEN_TONES[hash % OPEN_TONES.length]
}

/** The class list for a tone, or '' for none. */
export const toneClass = (tone) => (tone ? `tone tone-${tone}` : '')
