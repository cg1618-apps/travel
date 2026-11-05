/**
 * The sheet's 刪除模式, rendered for real: what gets selected, what the confirm
 * names, and what is handed on to delete.
 */

import { act } from 'react'
import { createRoot } from 'react-dom/client'

import { Grid } from './Grid'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const item = (id, name, fields = {}) => ({
  id,
  list_id: 1,
  name,
  detail: null,
  category: '衣服',
  bag: null,
  location: null,
  need: 'bring',
  quantity: null,
  quantity_packed: null,
  unit: null,
  status: 'not_packed',
  timing: 'whenever',
  needs_double_check: false,
  double_checked: false,
  notes: null,
  position: id,
  ...fields,
})

const ITEMS = [
  item(1, '襯衫'),
  item(2, '襪子', { timing: 'day_of' }),
  item(3, '護照', { category: '證件' }),
]

let container
let root

function render(props = {}) {
  const onBulkDelete = vi.fn()
  const element = (extra) => (
    <Grid
      items={ITEMS}
      categories={[]}
      locations={[]}
      adding={false}
      onPatch={() => {}}
      onDelete={() => {}}
      onAddMany={() => {}}
      onAddVariant={() => {}}
      onReorder={() => {}}
      onBulkDelete={onBulkDelete}
      {...props}
      {...extra}
    />
  )
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => root.render(element()))
  return onBulkDelete
}

const buttonNamed = (text, scope = document) =>
  [...scope.querySelectorAll('button')].find((button) => button.textContent.trim().startsWith(text))
const press = (element) => act(async () => element.click())
const checkbox = (name) => container.querySelector(`input[aria-label*="${name}"][type="checkbox"]`)
const enterMode = () => press(buttonNamed('刪除模式'))

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe('刪除模式', () => {
  it('shows no checkboxes until it is entered', async () => {
    render()
    expect(checkbox('襯衫')).toBeNull()
    await enterMode()
    expect(checkbox('襯衫')).not.toBeNull()
    expect(buttonNamed('刪除所選').disabled).toBe(true)
  })

  it('asks once, naming the selection, then hands on those ids', async () => {
    const onBulkDelete = render()
    await enterMode()
    await press(checkbox('襯衫'))
    await press(checkbox('護照'))
    expect(buttonNamed('刪除所選').textContent).toContain('2')

    await press(buttonNamed('刪除所選'))
    expect(document.body.textContent).toContain('刪除 2 個項目？')
    expect(document.body.textContent).toContain('襯衫')
    expect(document.body.textContent).toContain('護照')
    expect(onBulkDelete).not.toHaveBeenCalled()

    const dialog = document.querySelector('[role="dialog"], [role="alertdialog"]')
    await press(buttonNamed('刪除', dialog))
    expect(onBulkDelete.mock.calls[0][0]).toEqual([1, 3])
  })

  it('全選 takes only what the filter shows, so nothing hidden is deleted', async () => {
    const onBulkDelete = render()
    // 打包時機 出發當天 leaves only 襪子 showing.
    await press(buttonNamed('出發當天', container.querySelector('[aria-label="打包時機"]')))
    await enterMode()
    await press(container.querySelector('input[aria-label="全選"]'))
    expect(buttonNamed('刪除所選').textContent).toContain('1')

    await press(buttonNamed('刪除所選'))
    const dialog = document.querySelector('[role="dialog"], [role="alertdialog"]')
    await press(buttonNamed('刪除', dialog))
    expect(onBulkDelete.mock.calls[0][0]).toEqual([2])
  })

  it('does not delete a row selected and then filtered out', async () => {
    const onBulkDelete = render()
    await enterMode()
    await press(checkbox('襯衫'))
    await press(checkbox('襪子'))
    await press(buttonNamed('出發當天', container.querySelector('[aria-label="打包時機"]')))
    expect(buttonNamed('刪除所選').textContent).toContain('1')

    await press(buttonNamed('刪除所選'))
    const dialog = document.querySelector('[role="dialog"], [role="alertdialog"]')
    await press(buttonNamed('刪除', dialog))
    expect(onBulkDelete.mock.calls[0][0]).toEqual([2])
  })

  it('完成 leaves the mode and forgets the selection', async () => {
    render()
    await enterMode()
    await press(checkbox('襯衫'))
    await press(buttonNamed('完成'))
    expect(checkbox('襯衫')).toBeNull()

    await enterMode()
    expect(checkbox('襯衫').checked).toBe(false)
  })

  it('says so when a delete failed', async () => {
    render({ deleteFailed: true })
    await enterMode()
    expect(container.querySelector('[role="alert"]').textContent).toBe('無法刪除，請再試一次。')
  })
})
