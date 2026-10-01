import { describe, expect, it } from 'vitest'

import {
  CHECK_LABELS, CHECK_STATES, DAY_TYPE_LABELS, NEED_LABELS, NEEDS,
  STATUS_LABELS, TIMING_LABELS, checkState,
} from './labels'
import { TIMINGS } from './timing'

describe('labels', () => {
  it('has a display string for every stored value', () => {
    for (const s of ['not_packed', 'packed', 'no_need']) expect(STATUS_LABELS[s]).toBeTruthy()
    for (const t of TIMINGS) expect(TIMING_LABELS[t]).toBeTruthy()
    for (const n of NEEDS) expect(NEED_LABELS[n]).toBeTruthy()
    for (const c of CHECK_STATES) expect(CHECK_LABELS[c]).toBeTruthy()
    for (const d of ['weekday', 'holiday']) expect(DAY_TYPE_LABELS[d]).toBeTruthy()
  })

  it('uses the sheet words', () => {
    expect(STATUS_LABELS).toEqual({ not_packed: '未打包', packed: '已打包', no_need: '不需打包' })
    expect(TIMING_LABELS).toEqual({
      whenever: '隨時', night_before: '出發前晚', day_of: '出發當天', just_before: '出發前',
    })
    expect(NEED_LABELS).toEqual({ need: '需要', bring: '需帶', buy: '需買' })
    expect(CHECK_LABELS).toEqual({ off: '不需確認', needed: '未確認', done: '確認' })
  })

  it('derives the check state from the two fields', () => {
    expect(checkState({ needs_double_check: false, double_checked: false })).toBe('off')
    expect(checkState({ needs_double_check: true, double_checked: false })).toBe('needed')
    expect(checkState({ needs_double_check: true, double_checked: true })).toBe('done')
  })
})
