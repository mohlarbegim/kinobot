import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Prod: Django `/static/dashboard/` da beradi. Dev: oddiy `/`.
// Build natijasi Django `static/dashboard/` ga chiqadi -> collectstatic -> whitenoise.
export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/static/dashboard/' : '/',
  plugins: [react()],
  build: {
    outDir: '../static/dashboard',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
}))
