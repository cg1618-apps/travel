import { describe, expect, it, vi } from 'vitest'

import { required } from './cells'

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
