/**
 * The 備份 section's states, rendered for real against a stubbed `fetch` — the
 * one boundary `api/client.js` crosses. No testing library: `react-dom/client`
 * and `act` are enough for one button and its result.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act } from 'react'
import { createRoot } from 'react-dom/client'

import BackupSection from './BackupSection'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let container
let root

const json = (status, body) =>
  Promise.resolve(new Response(JSON.stringify(body), { status }))

function render() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => {
    root.render(
      <QueryClientProvider client={client}>
        <BackupSection />
      </QueryClientProvider>,
    )
  })
}

const button = () => container.querySelector('button')

async function press() {
  await act(async () => {
    button().click()
  })
}

/** Let the stubbed response settle and React re-render. */
async function settle() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0))
  })
}

beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('BackupSection', () => {
  it('starts idle: the heading, the restore hint and an enabled button', () => {
    render()
    expect(container.querySelector('h2').textContent).toBe('備份到 Google Sheets')
    expect(container.textContent).toContain('scripts/restore_sheet.py')
    expect(button().textContent).toBe('立即備份')
    expect(button().disabled).toBe(false)
    expect(container.querySelector('[role="alert"]')).toBeNull()
  })

  it('posts to /api/backup and disables the button while it runs', async () => {
    const fetch = vi.fn(() => new Promise(() => {}))
    vi.stubGlobal('fetch', fetch)
    render()
    await press()
    await settle()

    expect(fetch).toHaveBeenCalledWith('/api/backup', expect.objectContaining({ method: 'POST' }))
    expect(fetch.mock.calls[0][1].body).toBeUndefined()
    expect(button().disabled).toBe(true)
    expect(button().textContent).toBe('備份中…')
  })

  it('shows the Taipei time and the total row count on success', async () => {
    vi.stubGlobal('fetch', vi.fn(() =>
      json(200, {
        tabs: 12,
        rows: { packing_lists: 3, packing_items: 40, trips: 2 },
        // 06:30 UTC is 14:30 in Taipei.
        backed_up_at: '2026-10-07T06:30:00+00:00',
      }),
    ))
    render()
    await press()
    await settle()

    const status = container.querySelector('[role="status"]')
    expect(status.textContent).toContain('已備份')
    expect(status.textContent).toContain('10/07 14:30')
    expect(status.textContent).toContain('45 筆資料')
    expect(button().disabled).toBe(false)
    expect(button().textContent).toBe('立即備份')
  })

  it.each([
    [409, 'A backup is already running.', '已有備份正在進行，請稍後再試。'],
    [503, 'Google Sheets is not configured.', '無法使用 Google Sheets：連不上，或尚未設定。'],
    [422, 'Every table is empty.', '資料庫是空的，沒有可以備份的資料。'],
  ])('says what a %i means, with the status', async (status, detail, message) => {
    vi.stubGlobal('fetch', vi.fn(() => json(status, { detail })))
    render()
    await press()
    await settle()

    const alert = container.querySelector('[role="alert"]')
    expect(alert.textContent).toContain(message)
    expect(alert.textContent).toContain(`（${status}）`)
    // The English detail is not rendered; see docs/frontend.md.
    expect(alert.textContent).not.toContain(detail)
    expect(container.querySelector('[role="status"]')).toBeNull()
    expect(button().disabled).toBe(false)
  })
})
