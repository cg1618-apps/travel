import { describe, expect, it } from 'vitest'

import { LABEL_KIND_LABELS } from './labels'
import { OPTION_KINDS, kindFromSearch, optionCounts, searchForKind } from './options'

describe('OPTION_KINDS', () => {
  it('is every label kind, in the labels order', () => {
    expect(OPTION_KINDS).toEqual(['category', 'bag', 'location', 'ticket_type'])
    expect(OPTION_KINDS).toEqual(Object.keys(LABEL_KIND_LABELS))
  })
})

describe('kindFromSearch and searchForKind', () => {
  it('reads every kind back from its own search', () => {
    for (const kind of OPTION_KINDS) {
      expect(kindFromSearch(searchForKind(kind).tab ?? null)).toBe(kind)
    }
  })
  it('makes the first kind the bare URL', () => {
    expect(searchForKind('category')).toEqual({})
    expect(searchForKind('bag')).toEqual({ tab: 'bag' })
  })
  it('sends anything unknown to the first kind', () => {
    expect(kindFromSearch(null)).toBe('category')
    expect(kindFromSearch('free')).toBe('category')
    expect(kindFromSearch('')).toBe('category')
  })
})

describe('optionCounts', () => {
  it('counts per kind and keeps a zero for a kind with none', () => {
    const options = [
      { kind: 'category' }, { kind: 'category' }, { kind: 'ticket_type' }, { kind: 'unknown' },
    ]
    expect(optionCounts(options)).toEqual({ category: 2, bag: 0, location: 0, ticket_type: 1 })
  })
})
