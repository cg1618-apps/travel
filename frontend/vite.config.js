import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// outDir is outside frontend/ because uvicorn serves the built bundle from the
// repository root. port 5175 and the 8002 proxy are this app's slots in the
// box-wide allocation: uvicorn = the app's registry port, Vite = 5173 + (port
// - 8000), so all four apps run at once without collisions.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: { outDir: '../frontend_dist', emptyOutDir: true },
  server: {
    port: 5175,
    strictPort: true,
    proxy: {
      // 127.0.0.1, not localhost: uvicorn binds IPv4 only, but Node resolves
      // localhost to ::1 first on Windows and the proxy then fails with
      // ECONNREFUSED against a server that is plainly running. Copied from the
      // media tracker, which found it the hard way.
      '/api': { target: 'http://127.0.0.1:8002', changeOrigin: true },
    },
  },
})
