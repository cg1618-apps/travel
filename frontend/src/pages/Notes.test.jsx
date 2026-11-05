/**
 * 筆記's group arrows, rendered for real against a stubbed `fetch`: what each
 * press sends, and which arrows there are to press at all.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act } from 'react'
import { createRoot } from 'react-dom/client'

import Notes from './Notes'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const note = (id, group_name, position) => ({
  id,
  group_name,
  title: `note ${id}`,
  description: null,
  links: [],
  position,
})

/** Ungrouped ×1, 日本 ×2, 台灣 ×1, 韓國 ×1: a middle group, so both arrows can fire. */
const THREE_GROUPS = [
  note(1, null, 0),
  note(2, '日本', 1),
  note(3, '日本', 2),
  note(4, '台灣', 3),
  note(5, '韓國', 4),
]

const json = (body, status = 200) =>
  Promise.resolve(new Response(JSON.stringify(body), { status }))

let container
let root

/** `orderResponds` replaces the server's answer to a move; by default it keeps the order. */
async function render(notes, { orderResponds } = {}) {
  let stored = notes
  const fetchStub = vi.fn((url, options = {}) => {
    if (options.method !== 'PUT') return json(stored)
    const ids = JSON.parse(options.body).note_ids
    if (orderResponds) return orderResponds(ids)
    stored = reordered(stored, ids)
    return json(stored)
  })
  vi.stubGlobal('fetch', fetchStub)
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root.render(
      <QueryClientProvider client={client}>
        <Notes />
      </QueryClientProvider>,
    )
  })
  await until(() => expect(container.querySelector('h1')).not.toBeNull())
  return fetchStub
}

/**
 * Retries `assertion` until it holds, letting the page run between tries: a
 * save and the read after it take as many turns as the machine makes them
 * take, so no fixed wait is right on both a laptop and CI.
 */
const until = (assertion) =>
  vi.waitFor(async () => {
    await act(() => new Promise((resolve) => setTimeout(resolve)))
    assertion()
  })

function reordered(notes, ids) {
  return ids.map((id, position) => ({ ...notes.find((row) => row.id === id), position }))
}

const button = (label) => container.querySelector(`button[aria-label="${label}"]`)
const headings = () => [...container.querySelectorAll('h2')].map((h) => h.textContent)
const press = (label) => act(() => button(label).click())
const idle = (label) => until(() => expect(button(label).disabled).toBe(false))
const orderSent = (fetchStub) => {
  const put = fetchStub.mock.calls.find(([, options]) => options?.method === 'PUT')
  return put && JSON.parse(put[1].body).note_ids
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

describe('Notes group arrows', () => {
  it('moves a group down with its notes, the ungrouped note staying first', async () => {
    const fetchStub = await render(THREE_GROUPS)
    press('下移群組「日本」')
    await idle('下移群組「日本」')
    expect(orderSent(fetchStub)).toEqual([1, 4, 2, 3, 5])
    expect(fetchStub.mock.calls.find(([, o]) => o?.method === 'PUT')[0]).toBe('/api/notes/order')
    expect(headings()).toEqual(['台灣', '日本', '韓國'])
  })

  it('moves a group up', async () => {
    const fetchStub = await render(THREE_GROUPS)
    press('上移群組「韓國」')
    await idle('上移群組「韓國」')
    expect(orderSent(fetchStub)).toEqual([1, 2, 3, 5, 4])
    expect(headings()).toEqual(['日本', '韓國', '台灣'])
  })

  it('holds the arrows that would go past either end', async () => {
    await render(THREE_GROUPS)
    expect(button('上移群組「日本」').disabled).toBe(true)
    expect(button('下移群組「韓國」').disabled).toBe(true)
    // Mirror: the same groups' other arrows, and both of the middle group's, are live.
    expect(button('下移群組「日本」').disabled).toBe(false)
    expect(button('上移群組「韓國」').disabled).toBe(false)
    expect(button('上移群組「台灣」').disabled).toBe(false)
    expect(button('下移群組「台灣」').disabled).toBe(false)
  })

  it('offers no arrows when one named group has nowhere to go', async () => {
    await render([note(1, null, 0), note(2, '日本', 1)])
    expect(headings()).toEqual(['日本'])
    expect(container.querySelector('button[aria-label*="移群組"]')).toBeNull()
  })

  it('holds every arrow while a move is saving', async () => {
    let finish
    await render(THREE_GROUPS, {
      orderResponds: () => new Promise((resolve) => { finish = resolve }),
    })
    press('下移群組「日本」')
    await until(() => expect(finish).toBeTypeOf('function'))
    expect(button('下移群組「台灣」').disabled).toBe(true)
    expect(button('上移群組「韓國」').disabled).toBe(true)
    finish(new Response('[]'))
    await idle('上移群組「韓國」')
  })

  it('puts the order back and says so when a move is refused', async () => {
    await render(THREE_GROUPS, {
      orderResponds: () => json({ detail: 'refused' }, 422),
    })
    press('下移群組「日本」')
    await until(() => {
      expect(container.querySelector('[role="alert"]')?.textContent).toContain('排序沒有儲存')
      expect(headings()).toEqual(['日本', '台灣', '韓國'])
    })
  })

  it('no longer has a dialog for it', async () => {
    await render(THREE_GROUPS)
    // Three named groups: exactly what used to bring the button up.
    expect(headings()).toEqual(['日本', '台灣', '韓國'])
    const labels = [...container.querySelectorAll('button')].map((b) => b.textContent)
    expect(labels).not.toContain('排序群組')
  })
})
