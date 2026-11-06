/**
 * 備案 on a trip's card, rendered for real against a stubbed `fetch`: choosing
 * which option is the main one, what + 新增備案 starts with, and when a backup's
 * places are hidden.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import Trip from './Trip'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const leg = (id, fields = {}) => ({
  id,
  trip_id: 1,
  backup_of_id: null,
  from_place: '台北',
  to_place: '東京',
  // 09:30 in Taipei.
  departs_at: '2026-10-01T01:30:00Z',
  arrives_at: '2026-10-01T05:00:00Z',
  transport_type: 'other',
  direction: null,
  ride_type: null,
  section: null,
  service: null,
  service_number: null,
  seat: null,
  price: null,
  ticket_type: null,
  booked: false,
  paid: false,
  collected: false,
  booking_code: null,
  notes: null,
  packing_list_id: null,
  packing_list_name: null,
  has_booked: true,
  has_paid: true,
  has_collected: true,
  has_booking_code: true,
  backups: [],
  ...fields,
})

const tripWith = (legs) => ({
  id: 1,
  name: '東京',
  notes: null,
  kind: 'free',
  usage: 'unused',
  auto_saved_at: null,
  archive_note: null,
  done: false,
  ready: false,
  ticket_status: 'not_bought',
  round_trip: false,
  outbound_title: null,
  outbound_notes: null,
  return_title: null,
  return_notes: null,
  created_at: '2026-09-01T00:00:00Z',
  legs,
})

const json = (body, status = 200) =>
  Promise.resolve(new Response(JSON.stringify(body), { status }))

let container
let root

async function render(trip, { promoteStatus = 200 } = {}) {
  const fetchStub = vi.fn((url, options = {}) => {
    if (url.endsWith('/promote')) return json({}, promoteStatus)
    if (options.method === 'POST') return json(leg(99), 201)
    if (url === '/api/label-options') return json([])
    return json(trip)
  })
  vi.stubGlobal('fetch', fetchStub)
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root.render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={['/trips/1']}>
          <Routes>
            <Route path="/trips/:tripId" element={<Trip />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
  })
  await vi.waitFor(() => expect(container.querySelector('article')).not.toBeNull())
  return fetchStub
}

const backupsSection = () => container.querySelector('section[aria-label="備案"]')
const backupCard = () => backupsSection().querySelector('article')
const buttonNamed = (scope, text) =>
  [...scope.querySelectorAll('button')].find((button) => button.textContent.trim() === text)
const press = (element) => act(async () => element.click())

/** A RowMenu acts only after a gesture of its own, so give it one first. */
async function chooseFromMenu(card, label) {
  await press(card.querySelector('[aria-haspopup="menu"]'))
  await act(async () => {
    document.dispatchEvent(new Event('pointerdown'))
  })
  const item = [...document.querySelectorAll('[role="menuitem"]')].find(
    (candidate) => candidate.textContent === label,
  )
  await press(item)
}

const setValue = (element, value) =>
  act(async () => {
    const proto = element instanceof HTMLSelectElement ? HTMLSelectElement : HTMLInputElement
    Object.getOwnPropertyDescriptor(proto.prototype, 'value').set.call(element, value)
    element.dispatchEvent(new Event(element instanceof HTMLSelectElement ? 'change' : 'input', { bubbles: true }))
  })

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('choosing the main option', () => {
  const withBackup = () =>
    tripWith([leg(1, { backups: [leg(2, { backup_of_id: 1, from_place: '松山' })] })])

  it('promotes the backup from its menu', async () => {
    const fetchStub = await render(withBackup())
    await chooseFromMenu(backupCard(), '設為主要')
    await vi.waitFor(() =>
      expect(fetchStub).toHaveBeenCalledWith(
        '/api/trip-legs/2/promote',
        expect.objectContaining({ method: 'POST' }),
      ),
    )
  })

  it('offers it on a backup and not on the entry that is already the main one', async () => {
    await render(withBackup())
    await chooseMenuOpen(container.querySelector('article'))
    expect(menuLabels()).not.toContain('設為主要')
    expect(menuLabels()).toContain('刪除這段')
  })

  it('says so when the promotion fails', async () => {
    await render(withBackup(), { promoteStatus: 500 })
    await chooseFromMenu(backupCard(), '設為主要')
    await vi.waitFor(() =>
      expect(backupCard().querySelector('[role="alert"]').textContent).toBe('發生錯誤'),
    )
  })
})

async function chooseMenuOpen(card) {
  await press(card.querySelector('[aria-haspopup="menu"]'))
}

const menuLabels = () => [...document.querySelectorAll('[role="menuitem"]')].map((item) => item.textContent)

describe('+ 新增備案', () => {
  it("starts from the entry's places and departure, and no arrival", async () => {
    await render(tripWith([leg(1)]))
    await press(buttonNamed(backupsSection(), '+ 新增備案'))
    await setValue(backupsSection().querySelector('select[aria-label="類型"]'), 'other')

    expect(backupsSection().querySelector('input[aria-label="起點"]').value).toBe('台北')
    expect(backupsSection().querySelector('input[aria-label="終點"]').value).toBe('東京')
    expect(backupsSection().querySelector('input[aria-label="出發時間"]').value).toBe('2026-10-01T09:30')
    expect(backupsSection().querySelector('input[aria-label="抵達時間"]').value).toBe('')
  })

  it('leaves + 新增一段 empty', async () => {
    await render(tripWith([leg(1)]))
    await press(buttonNamed(container, '+ 新增一段'))
    // The form's select is the one that opens on 選擇類型; each card has its own.
    const select = [...container.querySelectorAll('select[aria-label="類型"]')].find((candidate) =>
      candidate.querySelector('option[disabled]'),
    )
    await setValue(select, 'other')
    const form = select.parentElement

    expect(form.querySelector('input[aria-label="起點"]').value).toBe('')
    expect(form.querySelector('input[aria-label="出發時間"]').value).toBe('')
  })

  it("reads the entry's places as they are when opened, again after a cancel", async () => {
    await render(tripWith([leg(1)]))
    await press(buttonNamed(backupsSection(), '+ 新增備案'))
    await setValue(backupsSection().querySelector('select[aria-label="類型"]'), 'other')
    await setValue(backupsSection().querySelector('input[aria-label="起點"]'), '改掉')
    await press(buttonNamed(backupsSection(), '取消'))

    await press(buttonNamed(backupsSection(), '+ 新增備案'))
    await setValue(backupsSection().querySelector('select[aria-label="類型"]'), 'other')
    expect(backupsSection().querySelector('input[aria-label="起點"]').value).toBe('台北')
  })
})

describe("a backup's places", () => {
  const heading = () => backupCard().querySelector('h3')
  const pencil = () => backupCard().querySelector('button[aria-label="編輯起點終點"]')

  it('are hidden when both match the entry, and open with ✎', async () => {
    await render(tripWith([leg(1, { backups: [leg(2, { backup_of_id: 1 })] })]))
    expect(heading()).toBeNull()

    await press(pencil())
    expect(heading().textContent).toContain('台北')
    expect(heading().textContent).toContain('東京')

    await press(pencil())
    expect(heading()).toBeNull()
  })

  it.each([
    ['起點', { from_place: '松山' }],
    ['終點', { to_place: '羽田' }],
  ])('show, with no ✎, when the %s differs', async (_, places) => {
    await render(tripWith([leg(1, { backups: [leg(2, { backup_of_id: 1, ...places })] })]))
    expect(heading()).not.toBeNull()
    expect(pencil()).toBeNull()
  })

  it("stay on the entry's own card, which has nothing to match", async () => {
    await render(tripWith([leg(1, { backups: [leg(2, { backup_of_id: 1 })] })]))
    expect(container.querySelector('article h3').textContent).toContain('台北')
  })
})
