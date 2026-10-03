import { describe, expect, it } from 'vitest'

import { CHECK_STATES, NEEDS } from './labels'
import { TIMINGS } from './timing'
import { CHECK_TONES, NEED_TONES, STATUS_TONES, TIMING_TONES, toneClass, toneForText } from './tones'

describe('tones', () => {
  it('names a tone (or deliberately none) for every closed value', () => {
    for (const status of ['not_packed', 'packed', 'no_need']) expect(status in STATUS_TONES).toBe(true)
    for (const state of CHECK_STATES) expect(state in CHECK_TONES).toBe(true)
    for (const timing of TIMINGS) expect(TIMING_TONES[timing]).toBeTruthy()
    for (const need of NEEDS) expect(NEED_TONES[need]).toBeTruthy()
  })

  it('gives the same text the same tone, and a blank none', () => {
    expect(toneForText('超商')).toBe(toneForText('超商'))
    expect(toneForText('')).toBeNull()
    expect(toneForText(null)).toBeNull()
  })

  it('builds a class list only for a tone', () => {
    expect(toneClass('green')).toBe('tone tone-green')
    expect(toneClass(null)).toBe('')
  })
})
