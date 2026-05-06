import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    globals: true,
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:18000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'http://localhost:18000',
        changeOrigin: true,
        ws: true,
      },
      '/events': {
        target: 'http://localhost:18000',
        changeOrigin: true,
      },
      '/go2rtc': {
        target: 'http://localhost:1984',
        changeOrigin: true,
        ws: true,
        rewrite: (path: string) => path.replace(/^\/go2rtc/, ''),
      },
    },
  },
})
