import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // The backend (backend/, `make api`) serves the API on 8190 without CORS.
    proxy: {
      '/api': 'http://127.0.0.1:8190',
    },
  },
})
