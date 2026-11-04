import { describe, expect, it } from 'vitest'

import {
  canSaveNote, formatPrice, groupByDayType, inIdOrder, linkText, moveTo, notePayload, optionSummary,
} from './transport'

describe('formatPrice', () => {
  it('shows a price with its currency', () => {
    expect(formatPrice(22)).toBe('NT$22')
  })
  it('shows a free ride as NT$0 rather than as unset', () => {
    expect(formatPrice(0)).toBe('NT$0')
  })
  it('leaves an unset price unset', () => {
    expect(formatPrice(null)).toBeNull()
  })
})

describe('groupByDayType', () => {
  const d = (id, day_type) => ({ id, day_type, time: '08:00', irregular: false })
  it('splits by day type whatever order the API sent', () => {
    const groups = groupByDayType([d(1, 'holiday'), d(2, 'weekday'), d(3, 'holiday')])
    expect(groups.weekday.map((x) => x.id)).toEqual([2])
    expect(groups.holiday.map((x) => x.id)).toEqual([1, 3])
  })
  it('always has both rows, empty when there are no departures', () => {
    expect(groupByDayType([])).toEqual({ weekday: [], holiday: [] })
  })
  it('keeps the weekday row first', () => {
    expect(Object.keys(groupByDayType([d(1, 'holiday')]))).toEqual(['weekday', 'holiday'])
  })
})

describe('optionSummary', () => {
  const option = { mode: '公車 307', price: 15, duration: '40分' }
  it('joins mode, price and duration', () => {
    expect(optionSummary(option)).toBe('公車 307 · NT$15 · 40分')
  })
  it('keeps a free ride, which is a price and not a gap', () => {
    expect(optionSummary({ ...option, price: 0 })).toBe('公車 307 · NT$0 · 40分')
  })
  it('leaves out what is unset', () => {
    expect(optionSummary({ mode: '步行', price: null, duration: null })).toBe('步行')
    expect(optionSummary({ ...option, price: null })).toBe('公車 307 · 40分')
  })
})

describe('moveTo', () => {
  it('moves one entry down and up', () => {
    expect(moveTo([1, 2, 3, 4], 0, 2)).toEqual([2, 3, 1, 4])
    expect(moveTo([1, 2, 3, 4], 3, 1)).toEqual([1, 4, 2, 3])
  })
  it('leaves the input alone', () => {
    const list = [1, 2]
    moveTo(list, 0, 1)
    expect(list).toEqual([1, 2])
  })
})

describe('inIdOrder', () => {
  const rows = [{ id: 1 }, { id: 2 }, { id: 3 }]
  it('puts rows in the order the ids name', () => {
    expect(inIdOrder(rows, [3, 1, 2]).map((row) => row.id)).toEqual([3, 1, 2])
  })
  it('keeps a row the ids do not name, at the end', () => {
    expect(inIdOrder(rows, [2, 1]).map((row) => row.id)).toEqual([2, 1, 3])
  })
})

describe('notePayload and canSaveNote', () => {
  const fields = (overrides) => ({ title: '', description: '', links: [], ...overrides })
  it('sends blanks as null and drops empty link inputs', () => {
    expect(notePayload(fields({ title: '  ', description: ' 第一行\n第二行 ', links: ['', ' https://a.example/x ', '  '] })))
      .toEqual({ title: null, description: '第一行\n第二行', links: ['https://a.example/x'] })
  })
  it('saves with a title alone or a link alone', () => {
    expect(canSaveNote(fields({ title: '轉乘' }))).toBe(true)
    expect(canSaveNote(fields({ links: ['https://a.example'] }))).toBe(true)
  })
  it('refuses a description alone, or only blank links', () => {
    expect(canSaveNote(fields({ description: '說明' }))).toBe(false)
    expect(canSaveNote(fields({ description: '說明', links: ['', ' '] }))).toBe(false)
  })
})

describe('linkText', () => {
  it('shows host and path without the scheme or a trailing slash', () => {
    expect(linkText('https://www.example.com/bus/307/')).toBe('www.example.com/bus/307')
    expect(linkText('https://example.com')).toBe('example.com')
  })
  it('shows anything that is not a URL as typed', () => {
    expect(linkText('not a url')).toBe('not a url')
  })
})
