import { resolve } from 'node:path'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": resolve(import.meta.dirname, "src") } },
  build: {
    // Separate HTML entries keep direct links usable on a static host.
    rollupOptions: {
      input: {
        main: resolve(import.meta.dirname, 'index.html'),
        signup: resolve(import.meta.dirname, 'signup.html'),
        matches: resolve(import.meta.dirname, 'matches.html'),
        app: resolve(import.meta.dirname, 'app/index.html'),
        contact: resolve(import.meta.dirname, 'contact/index.html'),
        privacy: resolve(import.meta.dirname, 'legal/privacy-policy/index.html'),
        terms: resolve(import.meta.dirname, 'legal/terms-of-service/index.html'),
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
