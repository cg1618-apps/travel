import { describe, expect, it } from 'vitest'

import { otherTheme, resolveTheme, storedChoice } from './theme'

describe('resolveTheme', () => {
  it('follows the OS when nothing is stored', () => {
    expect(resolveTheme(null, true)).toBe('dark')
    expect(resolveTheme(null, false)).toBe('light')
  })
  it('a stored choice beats the OS in both directions', () => {
    expect(resolveTheme('light', true)).toBe('light')
    expect(resolveTheme('dark', false)).toBe('dark')
  })
  it('reads a stored value it does not know as no choice', () => {
    expect(resolveTheme('system', true)).toBe('dark')
    expect(resolveTheme('', false)).toBe('light')
  })
})

describe('storedChoice', () => {
  it('keeps light and dark and nothing else', () => {
    expect(storedChoice('light')).toBe('light')
    expect(storedChoice('dark')).toBe('dark')
    expect(storedChoice('Dark')).toBeNull()
    expect(storedChoice(undefined)).toBeNull()
  })
})

describe('otherTheme', () => {
  it('flips', () => {
    expect(otherTheme('dark')).toBe('light')
    expect(otherTheme('light')).toBe('dark')
  })
})
