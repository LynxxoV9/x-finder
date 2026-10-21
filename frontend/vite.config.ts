import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Configuration Vite pour X-Finder avec proxy API vers FastAPI
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true
  }
})
