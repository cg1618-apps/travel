import { describe, expect, it } from 'vitest'

import { formatDuration, formatTaipei, fromTaipeiInput, taipeiInputValue } from './trips'

describe('formatDuration', () => {
  it('matches the sheet format', () => {
    expect(formatDuration('2026-09-24T18:06:00+08:00', '2026-09-24T20:59:00+08:00')).toBe('2h53m')
    expect(formatDuration('2026-09-28T12:15:00+08:00', '2026-09-28T14:23:00+08:00')).toBe('2h08m')
    expect(formatDuration('2026-09-28T12:15:00+08:00', '2026-09-28T12:22:00+08:00')).toBe('7m')
  })
})

describe('Taipei conversions', () => {
  it('shows a UTC instant in Taipei time', () => {
    expect(formatTaipei('2026-09-24T10:06:00Z')).toBe('Thu 09/24 18:06')
  })
  it('round-trips an input value', () => {
    expect(taipeiInputValue('2026-09-23T16:30:00Z')).toBe('2026-09-24T00:30')
    expect(fromTaipeiInput('2026-09-24T00:30')).toBe('2026-09-24T00:30:00+08:00')
  })
})
