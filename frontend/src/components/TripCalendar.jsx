/**
 * A month of days, Sunday first, with every day a trip covers marked and
 * linked to it. Today is circled. Only the month shown is state.
 */

import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { monthGrid, shiftMonth, taipeiToday, tripDays } from '../lib/calendar'

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']

function NavButton({ label, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className="min-h-9 min-w-9 rounded-md text-text-muted hover:bg-surface-2 hover:text-text"
    >
      {children}
    </button>
  )
}

function Day({ day, trips, isToday }) {
  const number = (
    <span
      className={`inline-flex size-7 items-center justify-center rounded-full tabular-nums ${
        isToday ? 'bg-brand font-semibold text-on-brand' : ''
      }`}
    >
      {day.day}
    </span>
  )
  const tone = day.inMonth ? 'text-text' : 'text-text-faint'
  if (trips.length === 0) {
    return <div className={`flex min-h-14 flex-col items-center p-1 ${tone}`}>{number}</div>
  }
  const names = trips.map((trip) => trip.name).join('、')
  return (
    <Link
      to={`/trips/${trips[0].id}`}
      title={names}
      aria-label={`${day.key}：${names}`}
      className={`flex min-h-14 flex-col items-center gap-0.5 bg-brand-soft p-1 no-underline hover:bg-surface-2 ${tone}`}
    >
      {number}
      {/* A name on a wide screen; a dot where a name would not fit. */}
      <span className="hidden w-full truncate text-center text-xs text-brand sm:block">{names}</span>
      <span className="size-1.5 rounded-full bg-brand sm:hidden" aria-hidden="true" />
    </Link>
  )
}

export default function TripCalendar({ trips }) {
  const today = taipeiToday()
  const [shown, setShown] = useState({ year: today.year, month: today.month })
  const byDay = useMemo(() => tripDays(trips), [trips])
  const isThisMonth = shown.year === today.year && shown.month === today.month

  return (
    <section className="mx-4 mt-4 rounded-lg border border-border bg-surface" aria-label="行程月曆">
      <div className="flex items-center gap-1 border-b border-border px-2 py-1">
        <NavButton label="上個月" onClick={() => setShown(shiftMonth(shown, -1))}>‹</NavButton>
        <h2 className="m-0 min-w-28 text-center text-base font-semibold tabular-nums">
          {shown.year} 年 {shown.month} 月
        </h2>
        <NavButton label="下個月" onClick={() => setShown(shiftMonth(shown, 1))}>›</NavButton>
        {!isThisMonth && (
          <button
            type="button"
            onClick={() => setShown({ year: today.year, month: today.month })}
            className="ml-auto rounded-md px-2 py-1 text-sm text-brand hover:bg-surface-2"
          >
            今天
          </button>
        )}
      </div>
      <div className="grid grid-cols-7 text-center text-xs text-text-faint">
        {WEEKDAYS.map((weekday) => (
          <div key={weekday} className="py-1.5">
            {weekday}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7 text-sm">
        {monthGrid(shown).flat().map((day) => (
          <Day
            key={day.key}
            day={day}
            trips={byDay.get(day.key) ?? []}
            isToday={day.key === today.key}
          />
        ))}
      </div>
    </section>
  )
}
