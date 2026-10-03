import { describe, expect, it } from 'vitest'

import { suggest } from './suggest'

const options = ['3C', '包包 / 袋子', '藥品 / 衛生', '重要', '小包包']

describe('suggest', () => {
  it('offers everything before anything is typed', () => {
    expect(suggest(options, '')).toEqual(options)
    expect(suggest(options, null)).toEqual(options)
  })

  it('narrows to what contains the text, prefix matches first', () => {
    expect(suggest(options, '包')).toEqual(['包包 / 袋子', '小包包'])
    expect(suggest(['3C', 'a3c'], '3c')).toEqual(['a3c'])
  })

  it('leaves out the option already typed in full', () => {
    expect(suggest(options, '重要')).toEqual([])
  })
})
