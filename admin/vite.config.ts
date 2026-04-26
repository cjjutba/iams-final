import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import { existsSync } from 'fs'

export default defineConfig({
  base: '/',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  // Pre-bundle deps that otherwise show up as "Outdated Optimize Dep 504"s
  // after a package.json change. Without this, every time a new dep lands,
  // the running dev server keeps serving old optimizer fingerprints and
  // the browser hits 504s until the cache is wiped + server restarted.
  // Listing the heavy/commonly-added-late deps here forces deterministic
  // pre-bundling on server start.
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-router-dom',
      'react-hook-form',
      '@hookform/resolvers/zod',
      'zod',
      'react-day-picker',
      'react-grab',
      'date-fns',
      'lucide-react',
      'axios',
      '@tanstack/react-query',
      '@tanstack/react-table',
      'zustand',
      'recharts',
      'sonner',
    ],
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
      // APK downloads from the landing page. Two-tier resolution:
      //   1. If admin/public/iams-{student,faculty}.apk exists (built locally
      //      via scripts/build-local-apks.sh), the bypass returns the same
      //      URL → next() falls through to Vite's public-dir middleware,
      //      which serves the local debug APK as-is.
      //   2. Otherwise the proxy forwards to the VPS at 167.71.217.44 so the
      //      Download buttons still work without a local build.
      // Production (Vercel) skips this entirely — admin/vercel.json rewrites
      // the same paths to GitHub release assets.
      '/iams-student.apk': {
        target: 'http://167.71.217.44',
        changeOrigin: true,
        bypass: (req) => {
          if (existsSync(path.resolve(__dirname, 'public/iams-student.apk'))) {
            return req.url
          }
        },
      },
      '/iams-faculty.apk': {
        target: 'http://167.71.217.44',
        changeOrigin: true,
        bypass: (req) => {
          if (existsSync(path.resolve(__dirname, 'public/iams-faculty.apk'))) {
            return req.url
          }
        },
      },
    },
  },
})
