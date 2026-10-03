import { describe, expect, it } from 'vitest'

import { draftProblems, emptyDraft, isBlank, toPayload } from './drafts'

describe('drafts', () => {
  it('gives every draft its own key', () => {
    expect(emptyDraft().key).not.toBe(emptyDraft().key)
  })

  it('treats an untouched row as blank, and any change as not', () => {
    expect(isBlank(emptyDraft())).toBe(true)
    expect(isBlank({ ...emptyDraft(), category: '3C' })).toBe(false)
    expect(isBlank({ ...emptyDraft(), timing: 'day_of' })).toBe(false)
  })

  it('refuses a row without a name or with a count that is not whole', () => {
    expect(draftProblems(emptyDraft())).toEqual(['name'])
    expect(draftProblems({ ...emptyDraft(), name: '襪子', quantity: '1.5' })).toEqual(['quantity'])
    expect(draftProblems({ ...emptyDraft(), name: '襪子', quantity_packed: 'x' })).toEqual([
      'quantity_packed',
    ])
    expect(draftProblems({ ...emptyDraft(), name: '襪子', quantity: '3' })).toEqual([])
  })

  it('sends blanks as null and Double Check as its two fields', () => {
    const payload = toPayload({
      ...emptyDraft(' 衣物 '),
      name: ' 襪子 ',
      quantity: '5',
      unit: '雙',
      check: 'needed',
      need: 'bring',
    })
    expect(payload).toEqual({
      name: '襪子',
      detail: null,
      category: '衣物',
      location: null,
      need: 'bring',
      quantity: 5,
      unit: '雙',
      quantity_packed: null,
      status: 'not_packed',
      timing: 'whenever',
      needs_double_check: true,
      double_checked: false,
      notes: null,
    })
  })
})
