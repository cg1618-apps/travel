/**
 * What each trip-entry 類型 shows: its fields, and per tick and the booking
 * code whether it is fixed, optional (with a default) or absent.
 *
 * The same table is `app/services/domain/leg_types.py`, which decides the
 * defaults on a write and refuses a flag the type does not allow; the two are
 * pinned by tests, so a change to one without the other goes red. The screen
 * reads this one to decide what a card and the add form show.
 *
 * Flags, as the API names them: `has_booked`, `has_paid`, `has_collected`
 * (the three ticks) and `has_booking_code` (the code). A fixed flag is always
 * true and shows no toggle; an absent one is always false and shows nothing;
 * an optional one is the entry's own choice, starting at its default.
 */

import { BOOKING_LABELS } from './labels'

export const FIXED = 'fixed'
export const ON = 'optional_on'
export const OFF = 'optional_off'
export const ABSENT = 'absent'

/** The ticks, in the order a card shows them; the code is a flag but not a tick. */
export const TICKS = ['booked', 'paid', 'collected']
export const FLAGS = [...TICKS, 'booking_code']
export const flagField = (flag) => `has_${flag}`

/** Field keys the API uses, in the order a card shows them. */
const RAIL = ['service', 'service_number', 'seat', 'price', 'ticket_type', 'direction']
const GENERAL = ['service', 'service_number', 'seat', 'price', 'ticket_type']

const BOOKABLE = { booked: ON, paid: ON, collected: ON, booking_code: ON }
const NONE = { booked: ABSENT, paid: ABSENT, collected: ABSENT, booking_code: ABSENT }
const ORDER = { booked: OFF, paid: OFF, collected: ABSENT, booking_code: OFF }

/** The spec's table, one row per 類型. */
export const LEG_TYPES = {
  hsr: { fields: RAIL, flags: { booked: FIXED, paid: FIXED, collected: FIXED, booking_code: FIXED } },
  train: { fields: RAIL, flags: BOOKABLE },
  coach: { fields: RAIL, flags: BOOKABLE },
  metro: { fields: ['service', 'price', 'direction'], flags: NONE },
  bus: { fields: ['service', 'service_number', 'price', 'direction'], flags: NONE },
  car: { fields: ['ride_type', 'service', 'service_number', 'seat', 'price'], flags: ORDER },
  bike: { fields: ['ride_type'], flags: ORDER },
  walk: { fields: [], flags: NONE },
  flight: { fields: GENERAL, flags: BOOKABLE },
  ship: { fields: GENERAL, flags: BOOKABLE },
  other: { fields: GENERAL, flags: BOOKABLE },
}

/** 開車 and 腳踏車 book an order, not a ticket. */
const ORDER_TYPES = ['car', 'bike']

/** The closed `ride_type` values a type offers; empty for every other type. */
export const RIDE_TYPES = {
  car: ['hail', 'own_car', 'car_rental'],
  bike: ['own_bike', 'youbike', 'moovo', 'bike_rental'],
}

const FIELD_LABELS = {
  service: '車種',
  service_number: '車號',
  seat: '座位',
  price: '價錢',
  ticket_type: '車票類型',
  direction: '方向',
}

/** An unknown type reads as 其他, the type every pre-existing entry became. */
const typeOf = (type) => LEG_TYPES[type] ?? LEG_TYPES.other

export const fieldsFor = (type) => typeOf(type).fields

export const flagMode = (type, flag) => typeOf(type).flags[flag]

/** 乘車類型 on 開車, 類型 on 腳踏車. */
export function fieldLabel(type, field) {
  if (field === 'ride_type') return type === 'car' ? '乘車類型' : '類型'
  return FIELD_LABELS[field]
}

/** A tick's or the code's name on this type: 已訂 and 訂單編號 on 開車 and 腳踏車. */
export function flagLabel(type, flag) {
  const order = ORDER_TYPES.includes(type)
  if (flag === 'booking_code') return order ? '訂單編號' : '訂票代碼'
  if (flag === 'booked' && order) return '已訂'
  return BOOKING_LABELS[flag]
}

/** Every flag at the type's default: fixed and optional-on true, the rest false. */
export function defaultFlags(type) {
  return Object.fromEntries(
    FLAGS.map((flag) => {
      const mode = flagMode(type, flag)
      return [flagField(flag), mode === FIXED || mode === ON]
    }),
  )
}

/** Whether this entry shows the flag at all: fixed always, optional when switched on. */
export function shows(leg, flag) {
  const mode = flagMode(leg.transport_type, flag)
  if (mode === ABSENT) return false
  return mode === FIXED || Boolean(leg[flagField(flag)])
}

/** The flags an entry may switch on or off: the type's optional ones. */
export const toggleableFlags = (type) =>
  FLAGS.filter((flag) => [ON, OFF].includes(flagMode(type, flag)))

/** The ticks an entry shows and has not ticked. The code is not a tick. */
export const untickedLabels = (leg) => TICKS.filter((tick) => shows(leg, tick) && !leg[tick])
