// Guard: the nav bar stays on screen, so anything else that sticks to the
// window has to pin below it. The height lives once in index.css as --nav-h,
// and the bar holds itself to it rather than wrapping to a second row, so the
// offsets can never disagree with what is on screen. A `top-0` here would tuck
// the header under the bar, and nothing but looking at it would say so.
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

const SRC = join(process.cwd(), 'src')
const read = (path) => readFileSync(join(SRC, path), 'utf8')

it('defines --nav-h in index.css', () => {
  expect(read('index.css')).toMatch(/--nav-h:/)
})

it('sticks the nav bar at the height the offsets assume, on one row', () => {
  const app = read('App.jsx')
  const bar = app.match(/<nav className="([^"]*)"/)[1]
  expect(bar).toMatch(/\bsticky\b/)
  expect(bar).toMatch(/\btop-0\b/)
  expect(bar).toContain('h-[var(--nav-h)]')
  expect(app).not.toMatch(/flex-wrap/)
})

it('keeps the nav bar under the z-50 dialogs and menus', () => {
  const bar = read('App.jsx').match(/<nav className="([^"]*)"/)[1]
  expect(bar).toMatch(/\bz-40\b/)
})

it.each(['pages/Trip.jsx', 'pages/Options.jsx'])('%s pins its sticky header below the nav', (page) => {
  const text = read(page)
  expect(text).toContain('sticky top-[var(--nav-h)]')
  expect(text).not.toMatch(/sticky top-0/)
})

// Grid has two shapes. Wide, the page scrolls and the header sticks to the
// window, so it clears the bar; narrow, it sticks to the top of its own box,
// where the bar is not in the way, but that box must fit below the bar.
describe('the sheet', () => {
  const grid = read('components/Grid.jsx')

  it('pins its header below the nav only where the window is what scrolls', () => {
    expect(grid).toContain('sticky top-0 min-[1160px]:top-[var(--nav-h)]')
  })

  it('sizes its scroller to the screen left under the nav', () => {
    expect(grid).toMatch(/max-h-\[calc\(100dvh\S*var\(--nav-h\)\S*\]/)
  })
})
