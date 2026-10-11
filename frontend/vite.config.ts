import { resolve } from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    // Two pages: the landing page and the sign-up page.
    rollupOptions: {
      input: {
        main: resolve(import.meta.dirname, 'index.html'),
        signup: resolve(import.meta.dirname, 'signup.html'),
      },
    },
  },
  server: {
    // The backend (backend/, `make api`) serves the API on 8190 without CORS.
    proxy: {
      '/api': 'http://127.0.0.1:8190',
    },
  },
})
