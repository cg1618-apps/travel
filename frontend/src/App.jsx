import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom'

import { useTheme } from './hooks/useTheme'
import Dashboard from './pages/Dashboard'
import Options from './pages/Options'
import PackingList from './pages/PackingList'
import PackingLists from './pages/PackingLists'
import Transport from './pages/Transport'
import TransportRoute from './pages/TransportRoute'
import Trip from './pages/Trip'
import Trips from './pages/Trips'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // This is one person's data on one device. Refetching on every window
      // focus buys nothing and costs a flicker every time you come back from
      // the airline's app.
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

// The app's name links to the dashboard; every screen is named in Traditional
// Chinese.
const NAV_LINKS = [
  ['/lists', '打包清單'],
  ['/transport', '交通'],
  ['/trips', '行程'],
  ['/options', '選項'],
]

/** ☾ or ☀: the theme the tap switches to, named for a screen reader. */
function ThemeToggle() {
  const { theme, toggle } = useTheme()
  const label = theme === 'dark' ? '切換成淺色模式' : '切換成深色模式'
  return (
    <button
      type="button"
      onClick={toggle}
      title={label}
      aria-label={label}
      aria-pressed={theme === 'dark'}
      className="ml-auto min-w-11 rounded-md text-ink-text/70 hover:text-ink-text"
    >
      {theme === 'dark' ? '☀' : '☾'}
    </button>
  )
}

function Nav() {
  return (
    <nav className="border-b border-border bg-ink text-ink-text">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3">
        <Link to="/" className="mr-2 font-semibold text-ink-text no-underline">
          travel
        </Link>
        {NAV_LINKS.map(([to, label]) => (
          <Link key={to} to={to} className="text-sm text-ink-text/70 no-underline">
            {label}
          </Link>
        ))}
        <ThemeToggle />
      </div>
    </nav>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Nav />
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/lists" element={<PackingLists />} />
          <Route path="/lists/:listId" element={<PackingList />} />
          <Route path="/transport" element={<Transport />} />
          <Route path="/transport/:routeId" element={<TransportRoute />} />
          <Route path="/trips" element={<Trips />} />
          {/* Old addresses, kept for bookmarks: the current trip, and the
              自動保存 page that is now a tab. /trips/auto-saved sits above
              /trips/:tripId, which would otherwise read it as an id. */}
          <Route path="/trip" element={<Navigate to="/trips" replace />} />
          <Route path="/trips/auto-saved" element={<Navigate to="/trips?tab=auto_saved" replace />} />
          <Route path="/trips/:tripId" element={<Trip />} />
          <Route path="/options" element={<Options />} />
          {/* The server's catch-all serves the bundle for any non-/api path,
              so an unknown URL reaches the router rather than a 404. */}
          <Route path="*" element={<Dashboard />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
