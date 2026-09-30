/**
 * Leg times. Stored as instants; always shown and entered in Asia/Taipei,
 * whatever timezone the viewing device is in.
 */

export const TAIPEI = 'Asia/Taipei'

export function formatDuration(departsAt, arrivesAt) {
  const total = Math.round((new Date(arrivesAt) - new Date(departsAt)) / 60000)
  const h = Math.floor(total / 60)
  const m = total % 60
  return h ? `${h}h${String(m).padStart(2, '0')}m` : `${m}m`
}

function parts(iso) {
  const fmt = new Intl.DateTimeFormat('en-US', {
    timeZone: TAIPEI, weekday: 'short', year: 'numeric', month: '2-digit',
    day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  })
  return Object.fromEntries(fmt.formatToParts(new Date(iso)).map((p) => [p.type, p.value]))
}

export function formatTaipei(iso) {
  const p = parts(iso)
  return `${p.weekday} ${p.month}/${p.day} ${p.hour}:${p.minute}`
}

export function taipeiInputValue(iso) {
  const p = parts(iso)
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`
}

/** Taiwan has no daylight saving, so the offset is always +08:00. */
export function fromTaipeiInput(value) {
  return `${value}:00+08:00`
}
