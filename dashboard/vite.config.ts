import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// base './' obligatorio: la app se publica en una subruta
export default defineConfig({
  base: './',
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:8000' } },
})
