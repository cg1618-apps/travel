import { describe, expect, it } from 'vitest'

import { parseWholeNumber } from './numbers'

describe('parseWholeNumber', () => {
  it('reads a whole number', () => {
    expect(parseWholeNumber(' 22 ')).toBe(22)
    expect(parseWholeNumber('0')).toBe(0)
  })
  it('reads an empty cell as clearing the value', () => {
    expect(parseWholeNumber('  ')).toBeNull()
  })
  it('refuses what is not a whole number', () => {
    expect(parseWholeNumber('NT$22')).toBeUndefined()
    expect(parseWholeNumber('-5')).toBeUndefined()
    expect(parseWholeNumber('1.5')).toBeUndefined()
    expect(parseWholeNumber('1e2')).toBeUndefined()
    expect(parseWholeNumber('兩')).toBeUndefined()
  })
})
