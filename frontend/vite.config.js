import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// outDir is outside frontend/ because uvicorn serves the built bundle from the
// repository root. port 5175 and the 8002 proxy are this app's slots in the
// box-wide allocation: uvicorn = the app's registry port, Vite = 5173 + (port
// - 8000), so all four apps run at once without collisions.
export default defineConfig({
  plugins: [react()],
  build: { outDir: '../frontend_dist', emptyOutDir: true },
  server: {
    port: 5175,
    strictPort: true,
    proxy: { '/api': 'http://localhost:8002' },
  },
})
