import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'

import Options from './pages/Options'
import PackingList from './pages/PackingList'
import PackingLists from './pages/PackingLists'

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

function Nav() {
  return (
    <nav className="border-b border-border bg-ink text-ink-text">
      <div className="mx-auto flex max-w-2xl items-center justify-between px-4 py-3">
        <Link to="/" className="font-semibold text-ink-text no-underline">
          travel
        </Link>
        <Link to="/options" className="text-sm text-ink-text/70 no-underline">
          Options
        </Link>
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
          <Route path="/" element={<PackingLists />} />
          <Route path="/lists/:listId" element={<PackingList />} />
          <Route path="/options" element={<Options />} />
          {/* The server's catch-all serves the bundle for any non-/api path,
              so an unknown URL reaches the router rather than a 404. */}
          <Route path="*" element={<PackingLists />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
