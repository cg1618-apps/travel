import { describe, expect, it } from 'vitest'

import {
  CHECK_LABELS, CHECK_STATES, DAY_TYPE_LABELS, KIND_LABELS, NEED_LABELS, NEEDS,
  STATUS_LABELS, TIMING_LABELS, USAGE_LABELS, USAGES, checkState,
} from './labels'
import { TIMINGS } from './timing'

describe('labels', () => {
  it('has a display string for every stored value', () => {
    for (const s of ['not_packed', 'packed', 'no_need']) expect(STATUS_LABELS[s]).toBeTruthy()
    for (const t of TIMINGS) expect(TIMING_LABELS[t]).toBeTruthy()
    for (const n of NEEDS) expect(NEED_LABELS[n]).toBeTruthy()
    for (const c of CHECK_STATES) expect(CHECK_LABELS[c]).toBeTruthy()
    for (const d of ['weekday', 'holiday']) expect(DAY_TYPE_LABELS[d]).toBeTruthy()
    for (const k of ['template', 'saved', 'free']) expect(KIND_LABELS[k]).toBeTruthy()
    for (const u of USAGES) expect(USAGE_LABELS[u]).toBeTruthy()
  })

  it('uses the sheet words', () => {
    expect(STATUS_LABELS).toEqual({ not_packed: '未打包', packed: '已打包', no_need: '不需打包' })
    expect(TIMING_LABELS).toEqual({
      whenever: '隨時', night_before: '出發前晚', day_of: '出發當天', just_before: '出發前',
    })
    expect(NEED_LABELS).toEqual({ need: '需要', bring: '需帶', buy: '需買' })
    expect(CHECK_LABELS).toEqual({ off: '不需確認', needed: '未確認', done: '確認' })
    expect(KIND_LABELS).toEqual({ template: '範本', saved: '保存', free: '一般' })
    expect(USAGE_LABELS).toEqual({
      in_use: '使用中', upcoming: '未來使用', unused: '未使用', past: '過去使用',
    })
  })

  it('derives the check state from the two fields', () => {
    expect(checkState({ needs_double_check: false, double_checked: false })).toBe('off')
    expect(checkState({ needs_double_check: true, double_checked: false })).toBe('needed')
    expect(checkState({ needs_double_check: true, double_checked: true })).toBe('done')
  })
})
