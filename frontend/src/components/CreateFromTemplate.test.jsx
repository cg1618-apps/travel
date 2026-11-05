/** The button on a 範本's page, and what it refuses until it has what it needs. */

import { act } from 'react'
import { createRoot } from 'react-dom/client'

import { CreateFromTemplate } from './CreateFromTemplate'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let container
let root

function render(props) {
  const onCreate = vi.fn()
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  act(() =>
    root.render(
      <CreateFromTemplate template={{ name: '札幌（範本）' }} noun="行程" onCreate={onCreate} {...props} />,
    ),
  )
  return onCreate
}

const buttonNamed = (name) =>
  [...container.querySelectorAll('button')].find((button) => button.textContent === name)
const open = () => act(() => container.querySelector('button').click())

function fill(input, value) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
  act(() => {
    setter.call(input, value)
    input.dispatchEvent(new Event('input', { bubbles: true }))
  })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe('CreateFromTemplate', () => {
  it('is a button until pressed', () => {
    render()
    expect(container.querySelector('button').textContent).toBe('+ 從這份範本建立行程')
    expect(container.querySelector('input')).toBeNull()
  })

  it('fills the name from the template, without its （範本）', () => {
    render()
    open()
    expect(container.querySelector('input').value).toBe('札幌')
  })

  it('creates with the name and no date when no date is needed', () => {
    const onCreate = render()
    open()
    act(() => buttonNamed('建立').click())
    expect(onCreate).toHaveBeenCalledWith({ name: '札幌', date: null })
  })

  it('holds 建立 until a required date is chosen, then sends it', () => {
    const onCreate = render({ dateRequired: true })
    open()
    expect(buttonNamed('建立').disabled).toBe(true)
    act(() => buttonNamed('建立').click())
    expect(onCreate).not.toHaveBeenCalled()
    // Mirror: the same form with the date is allowed.
    fill(container.querySelector('input[type="date"]'), '2026-12-01')
    expect(buttonNamed('建立').disabled).toBe(false)
    act(() => buttonNamed('建立').click())
    expect(onCreate).toHaveBeenCalledWith({ name: '札幌', date: '2026-12-01' })
  })

  it('holds 建立 while the name is blank', () => {
    render()
    open()
    fill(container.querySelector('input'), '   ')
    expect(buttonNamed('建立').disabled).toBe(true)
  })

  it('取消 closes the form and forgets what was typed', () => {
    render()
    open()
    fill(container.querySelector('input'), '別的名字')
    act(() => buttonNamed('取消').click())
    open()
    expect(container.querySelector('input').value).toBe('札幌')
  })
})
