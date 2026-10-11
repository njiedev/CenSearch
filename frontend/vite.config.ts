import { resolve } from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    // Pages: the landing page, sign-up, the earlier viewfinder design and the matches mock.
    rollupOptions: {
      input: {
        main: resolve(import.meta.dirname, 'index.html'),
        signup: resolve(import.meta.dirname, 'signup.html'),
        viewfinder: resolve(import.meta.dirname, 'viewfinder.html'),
        matches: resolve(import.meta.dirname, 'matches.html'),
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
