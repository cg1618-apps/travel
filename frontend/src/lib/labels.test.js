import { describe, expect, it } from 'vitest'

import {
  BOOKING_LABELS, CHECK_LABELS, CHECK_STATES, DAY_TYPE_LABELS, DONE_LABEL, KIND_LABELS,
  NEED_LABELS, NEEDS, NOT_DONE_LABEL, RIDE_TYPE_LABELS, STATUS_LABELS, TICKET_STATUS_LABELS,
  TICKET_STATUSES, TIMING_LABELS, TRANSPORT_TYPE_LABELS, TRANSPORT_TYPES, USAGE_LABELS, USAGES,
  checkState,
} from './labels'
import { RIDE_TYPES } from './legTypes'
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
    for (const t of TRANSPORT_TYPES) expect(TRANSPORT_TYPE_LABELS[t]).toBeTruthy()
    for (const r of Object.values(RIDE_TYPES).flat()) expect(RIDE_TYPE_LABELS[r]).toBeTruthy()
    for (const s of TICKET_STATUSES) expect(TICKET_STATUS_LABELS[s]).toBeTruthy()
    for (const b of ['booked', 'paid', 'collected']) expect(BOOKING_LABELS[b]).toBeTruthy()
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
    expect(BOOKING_LABELS).toEqual({ booked: '已訂票', paid: '已付款', collected: '已取票' })
    expect([DONE_LABEL, NOT_DONE_LABEL]).toEqual(['已準備完成', '未準備完成'])
    expect(TICKET_STATUS_LABELS).toEqual({
      not_bought: '未買票', not_needed: '無需買票', bought: '已買票',
    })
    expect(TRANSPORT_TYPE_LABELS).toEqual({
      hsr: '高鐵', train: '火車', metro: '捷運', bus: '公車', coach: '客運', car: '開車',
      bike: '腳踏車', walk: '走路', flight: '飛機', ship: '船', other: '其他',
    })
    expect(RIDE_TYPE_LABELS).toEqual({
      hail: '叫車', own_car: '自駕自己的車', car_rental: '租車',
      own_bike: '自己的', youbike: 'YouBike', moovo: 'Moovo', bike_rental: '租車',
    })
  })

  it('derives the check state from the two fields', () => {
    expect(checkState({ needs_double_check: false, double_checked: false })).toBe('off')
    expect(checkState({ needs_double_check: true, double_checked: false })).toBe('needed')
    expect(checkState({ needs_double_check: true, double_checked: true })).toBe('done')
  })
})
