import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  base: '/',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api/v1/ws': {
        target: 'ws://192.168.88.17',
        ws: true,
        changeOrigin: true,
      },
      '/api': {
        target: 'http://192.168.88.17',
        changeOrigin: true,
      },
      // Admin live-feed WHEP endpoint. Always targets the local mediamtx —
      // in local/onprem modes mediamtx runs on this Mac at :8889. Not mode-toggled
      // because Vercel admin (production mode) doesn't use the live feed.
      '/whep': {
        target: 'http://localhost:8889',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/whep/, ''),
      },
    },
  },
})
