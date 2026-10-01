import { describe, expect, it } from 'vitest'

import { tapStatus } from './status'

describe('tapStatus', () => {
  it('toggles between not packed and packed', () => {
    expect(tapStatus('not_packed')).toBe('packed')
    expect(tapStatus('packed')).toBe('not_packed')
  })
  it('brings no_need back to not packed rather than cycling through it', () => {
    expect(tapStatus('no_need')).toBe('not_packed')
  })
})
