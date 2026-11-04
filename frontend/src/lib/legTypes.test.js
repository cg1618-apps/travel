import { describe, expect, it } from 'vitest'

import { TRANSPORT_TYPES } from './labels'
import {
  ABSENT, FIXED, FLAGS, LEG_TYPES, OFF, ON, RIDE_TYPES, defaultFlags, fieldLabel, fieldsFor,
  flagLabel, flagMode, shows, toggleableFlags, untickedLabels,
} from './legTypes'

// The spec's table, written out once more so a change to LEG_TYPES has to be
// made on purpose. `leg_types.py` is pinned to the same rows.
const TABLE = {
  hsr: ['車種 車號 座位 價錢 車票類型 方向', [FIXED, FIXED, FIXED, FIXED]],
  train: ['車種 車號 座位 價錢 車票類型 方向', [ON, ON, ON, ON]],
  coach: ['車種 車號 座位 價錢 車票類型 方向', [ON, ON, ON, ON]],
  metro: ['車種 價錢 方向', [ABSENT, ABSENT, ABSENT, ABSENT]],
  bus: ['車種 車號 價錢 方向', [ABSENT, ABSENT, ABSENT, ABSENT]],
  car: ['乘車類型 車種 車號 座位 價錢', [OFF, OFF, ABSENT, OFF]],
  bike: ['類型', [OFF, OFF, ABSENT, OFF]],
  walk: ['', [ABSENT, ABSENT, ABSENT, ABSENT]],
  flight: ['車種 車號 座位 價錢 車票類型', [ON, ON, ON, ON]],
  ship: ['車種 車號 座位 價錢 車票類型', [ON, ON, ON, ON]],
  other: ['車種 車號 座位 價錢 車票類型', [ON, ON, ON, ON]],
}

describe('LEG_TYPES', () => {
  it('has a row for every 類型 and nothing else', () => {
    expect(Object.keys(LEG_TYPES).sort()).toEqual([...TRANSPORT_TYPES].sort())
  })

  for (const [type, [fields, flags]] of Object.entries(TABLE)) {
    it(`${type}: fields and flags as the spec's table`, () => {
      expect(fieldsFor(type).map((field) => fieldLabel(type, field)).join(' ')).toBe(fields)
      expect(FLAGS.map((flag) => flagMode(type, flag))).toEqual(flags)
    })
  }

  it('reads an unknown type as 其他', () => {
    expect(fieldsFor('teleport')).toEqual(fieldsFor('other'))
  })
})

describe('flagLabel', () => {
  it('says 已訂 and 訂單編號 on 開車 and 腳踏車 only', () => {
    for (const type of ['car', 'bike']) {
      expect(flagLabel(type, 'booked')).toBe('已訂')
      expect(flagLabel(type, 'booking_code')).toBe('訂單編號')
    }
    for (const type of ['hsr', 'train', 'other']) {
      expect(flagLabel(type, 'booked')).toBe('已訂票')
      expect(flagLabel(type, 'booking_code')).toBe('訂票代碼')
    }
    expect(flagLabel('car', 'paid')).toBe('已付款')
    expect(flagLabel('hsr', 'collected')).toBe('已取票')
  })
})

describe('RIDE_TYPES', () => {
  it('offers 乘車類型 on 開車 and 類型 on 腳踏車', () => {
    expect(RIDE_TYPES.car).toEqual(['hail', 'own_car', 'car_rental'])
    expect(RIDE_TYPES.bike).toEqual(['own_bike', 'youbike', 'moovo', 'bike_rental'])
    expect(fieldLabel('car', 'ride_type')).toBe('乘車類型')
    expect(fieldLabel('bike', 'ride_type')).toBe('類型')
  })
})

describe('defaultFlags and toggleableFlags', () => {
  it('turns fixed and optional-on flags on, the rest off', () => {
    expect(defaultFlags('hsr')).toEqual({
      has_booked: true, has_paid: true, has_collected: true, has_booking_code: true,
    })
    expect(defaultFlags('car')).toEqual({
      has_booked: false, has_paid: false, has_collected: false, has_booking_code: false,
    })
    expect(defaultFlags('train')).toEqual({
      has_booked: true, has_paid: true, has_collected: true, has_booking_code: true,
    })
    expect(defaultFlags('walk')).toEqual({
      has_booked: false, has_paid: false, has_collected: false, has_booking_code: false,
    })
  })
  it('offers a toggle only for optional flags', () => {
    expect(toggleableFlags('hsr')).toEqual([])
    expect(toggleableFlags('metro')).toEqual([])
    expect(toggleableFlags('car')).toEqual(['booked', 'paid', 'booking_code'])
    expect(toggleableFlags('other')).toEqual(FLAGS)
  })
})

describe('shows and untickedLabels', () => {
  const leg = (transport_type, fields = {}) => ({
    transport_type, booked: false, paid: false, collected: false,
    has_booked: false, has_paid: false, has_collected: false, has_booking_code: false, ...fields,
  })
  it('shows a fixed flag even when the row says off, and never an absent one', () => {
    expect(shows(leg('hsr'), 'booked')).toBe(true)
    expect(shows(leg('metro', { has_booked: true }), 'booked')).toBe(false)
  })
  it('shows an optional flag only when the entry turned it on', () => {
    expect(shows(leg('car'), 'paid')).toBe(false)
    expect(shows(leg('car', { has_paid: true }), 'paid')).toBe(true)
  })
  it('lists the shown ticks that are not ticked, never the code', () => {
    expect(untickedLabels(leg('hsr', { booked: true }))).toEqual(['paid', 'collected'])
    expect(untickedLabels(leg('car', { has_paid: true, has_booking_code: true }))).toEqual(['paid'])
    expect(untickedLabels(leg('walk'))).toEqual([])
  })
})
