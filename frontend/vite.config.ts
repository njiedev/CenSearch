import { resolve } from 'node:path'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": resolve(import.meta.dirname, "src") } },
  build: {
    // One HTML file per page keeps direct links working on any static host
    // without rewrite rules.
    rollupOptions: {
      input: {
        main: resolve(import.meta.dirname, 'index.html'),
        signup: resolve(import.meta.dirname, 'signup/index.html'),
        login: resolve(import.meta.dirname, 'login/index.html'),
        app: resolve(import.meta.dirname, 'app/index.html'),
        contact: resolve(import.meta.dirname, 'contact/index.html'),
        privacy: resolve(import.meta.dirname, 'legal/privacy-policy/index.html'),
        terms: resolve(import.meta.dirname, 'legal/terms-of-service/index.html'),
      },
    },
  },
  server: {
    open: '/',
    // Only used with `npm run dev:backend`; the backend (`make api`) serves the
    // API on 8190 without CORS.
    proxy: {
      '/api': 'http://127.0.0.1:8190',
    },
  },
})
