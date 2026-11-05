/**
 * The height follows the text. jsdom lays nothing out, so `scrollHeight` is
 * stubbed as 20px a line - the one number the component reads - and what is
 * checked is that it reads it again on every change.
 */

import { act, useState } from 'react'
import { createRoot } from 'react-dom/client'

import { AutoGrowTextarea } from './AutoGrowTextarea'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let container
let root

function Controlled({ initial }) {
  const [value, setValue] = useState(initial)
  return <AutoGrowTextarea value={value} onChange={(event) => setValue(event.target.value)} />
}

function render(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => root.render(element))
  return container.querySelector('textarea')
}

function type(textarea, value) {
  const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set
  act(() => {
    setter.call(textarea, value)
    textarea.dispatchEvent(new Event('input', { bubbles: true }))
  })
}

beforeEach(() => {
  vi.spyOn(HTMLTextAreaElement.prototype, 'scrollHeight', 'get').mockImplementation(function lines() {
    return this.value.split('\n').length * 20
  })
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.restoreAllMocks()
})

describe('AutoGrowTextarea', () => {
  it('opens as tall as the text it was given', () => {
    expect(render(<Controlled initial={'一\n二\n三'} />).style.height).toBe('60px')
  })

  it('grows and shrinks as lines are typed and removed', () => {
    const textarea = render(<Controlled initial="一" />)
    expect(textarea.style.height).toBe('20px')
    type(textarea, '一\n二')
    expect(textarea.style.height).toBe('40px')
    type(textarea, '一')
    expect(textarea.style.height).toBe('20px')
  })

  it('adds the border, which scrollHeight leaves out', () => {
    vi.spyOn(HTMLTextAreaElement.prototype, 'offsetHeight', 'get').mockReturnValue(22)
    vi.spyOn(HTMLTextAreaElement.prototype, 'clientHeight', 'get').mockReturnValue(20)
    expect(render(<Controlled initial="一" />).style.height).toBe('22px')
  })

  it('passes its rows on as the smallest height', () => {
    expect(render(<AutoGrowTextarea value="" rows={3} readOnly />).rows).toBe(3)
  })
})
