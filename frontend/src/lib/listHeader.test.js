import { describe, expect, it } from 'vitest'

import { leavingText, progressParts } from './listHeader'

const today = new Date(2026, 8, 30)

describe('leavingText', () => {
  it('says there is no date when there is none', () => {
    expect(leavingText(null, 'list', today)).toBe('未設定日期')
  })

  it('names today, tomorrow, later and past departures', () => {
    expect(leavingText('2026-09-30', 'list', today)).toBe('今天出發 · 2026-09-30')
    expect(leavingText('2026-10-01', 'list', today)).toBe('明天出發 · 2026-10-01')
    expect(leavingText('2026-10-03', 'list', today)).toBe('3 天後出發 · 2026-10-03')
    expect(leavingText('2026-09-28', 'list', today)).toBe('已出發 2 天 · 2026-09-28')
  })

  it('says the date comes from This time when a leg sets it, and not otherwise', () => {
    expect(leavingText('2026-10-01', 'trip_leg', today)).toBe(
      '明天出發 · 2026-10-01 · 由 This time 行程設定',
    )
    expect(leavingText('2026-10-01', 'list', today)).not.toContain('This time')
  })
})

const item = (status, needs = false, checked = false) => ({
  status,
  needs_double_check: needs,
  double_checked: checked,
})

describe('progressParts', () => {
  it('reports nothing for an empty list', () => {
    expect(progressParts([])).toBeNull()
  })

  it('counts no_need as settled and reports outstanding checks', () => {
    const parts = progressParts([item('packed'), item('no_need'), item('not_packed', true)])
    expect(parts).toEqual({ settled: '已處理 2 / 3', unchecked: ' · 1 項待確認', ready: null })
  })

  it('is ready only when everything is settled and checked', () => {
    expect(progressParts([item('packed', true, true), item('no_need')]).ready).toBe(
      ' · 可以出發了',
    )
    expect(progressParts([item('packed', true, false)]).ready).toBeNull()
  })
})
