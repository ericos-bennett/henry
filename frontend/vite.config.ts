import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // changeOrigin: false (the default for this object form, spelled out here since
      // the shorthand string form implies changeOrigin: true) preserves the browser's
      // original Host header so it keeps matching the Origin header on the way to the
      // backend - otherwise Django's CSRF check rejects every request, regardless of
      // which LAN device it came from.
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false },
    },
  },
})
