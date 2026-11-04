import { describe, expect, it, vi } from 'vitest'

import { remarkValue, required } from './cells'

describe('required', () => {
  it('passes a value through to the commit', () => {
    const commit = vi.fn()
    required(commit)('台北')
    expect(commit).toHaveBeenCalledWith('台北')
  })
  it('drops an emptied cell, so the field keeps its value', () => {
    // TextCell commits a blanked cell as null.
    const commit = vi.fn()
    required(commit)(null)
    required(commit)('')
    expect(commit).not.toHaveBeenCalled()
  })
})

describe('remarkValue', () => {
  it('keeps the lines as typed, without trailing blank lines', () => {
    expect(remarkValue('第一行\n  第二行\n\n')).toBe('第一行\n  第二行')
  })
  it('sends nothing but whitespace as null', () => {
    expect(remarkValue('')).toBeNull()
    expect(remarkValue(' \n ')).toBeNull()
  })
})
