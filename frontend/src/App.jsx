import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'

import AutoSavedTrips from './pages/AutoSavedTrips'
import Dashboard from './pages/Dashboard'
import Options from './pages/Options'
import PackingList from './pages/PackingList'
import PackingLists from './pages/PackingLists'
import Transport from './pages/Transport'
import Trip from './pages/Trip'

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
  ['/trip', '行程'],
  ['/options', '選項'],
]

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
          <Route path="/trip" element={<Trip />} />
          {/* Above /trips/:tripId, which would otherwise read it as an id. */}
          <Route path="/trips/auto-saved" element={<AutoSavedTrips />} />
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
