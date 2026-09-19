import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Tests sit beside the source they cover, as the media tracker's do.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
