import { describe, expect, it, vi } from 'vitest'

import { itemTitle, rowActions } from './rowMenu'

const item = (overrides = {}) => ({
  id: 7,
  name: '鑰匙',
  detail: null,
  category: '重要',
  status: 'not_packed',
  needs_double_check: false,
  double_checked: false,
  ...overrides,
})

const handlers = () => ({ onPatch: vi.fn(), onAddVariant: vi.fn(), onDelete: vi.fn() })

describe('itemTitle', () => {
  it('joins name and detail, or is just the name', () => {
    expect(itemTitle(item({ detail: '家鑰匙' }))).toBe('鑰匙 · 家鑰匙')
    expect(itemTitle(item())).toBe('鑰匙')
  })
})

describe('rowActions', () => {
  it('offers no_need on a row that is not no_need, and sets it', () => {
    const h = handlers()
    const [first] = rowActions(item(), h)
    expect(first.label).toBe('設為不需打包')
    first.onSelect()
    expect(h.onPatch).toHaveBeenCalledWith(7, { status: 'no_need' })
  })

  it('offers the way back on a no_need row', () => {
    const h = handlers()
    const [first] = rowActions(item({ status: 'no_need' }), h)
    expect(first.label).toBe('改回未打包')
    first.onSelect()
    expect(h.onPatch).toHaveBeenCalledWith(7, { status: 'not_packed' })
  })

  it('adds a variant of the row and hands the whole row to delete, last and marked danger', () => {
    const h = handlers()
    const actions = rowActions(item(), h)
    expect(actions.map((a) => a.label)).toEqual(['設為不需打包', '新增變化', '刪除'])
    actions[1].onSelect()
    expect(h.onAddVariant).toHaveBeenCalledWith(expect.objectContaining({ id: 7 }))
    expect(actions[2].danger).toBe(true)
    actions[2].onSelect()
    expect(h.onDelete).toHaveBeenCalledWith(expect.objectContaining({ id: 7, name: '鑰匙' }))
  })

  it('adds the three Double Check states only when asked, marking the current one', () => {
    const h = handlers()
    const actions = rowActions(item({ needs_double_check: true }), { ...h, withChecks: true })
    expect(actions.map((a) => a.label)).toEqual([
      '設為不需打包',
      '新增變化',
      'Double Check：不需確認',
      'Double Check：未確認 ✓',
      'Double Check：確認',
      '刪除',
    ])
    actions[4].onSelect()
    expect(h.onPatch).toHaveBeenCalledWith(7, { needs_double_check: true, double_checked: true })
  })
})
