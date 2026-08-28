import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Loads every key from frontend/.env* (no VITE_ prefix filter). These configure
  // the dev server only - production is `npm run build` + Caddy, which ignores this.
  const env = loadEnv(mode, process.cwd(), '')

  // Extra Host headers the dev server will accept, comma-separated (e.g. a LAN
  // hostname or a tunnel domain). Localhost/127.0.0.1 are always allowed.
  const allowedHosts = (env.ALLOWED_HOSTS ?? '')
    .split(',')
    .map((h) => h.trim())
    .filter(Boolean)

  // Where /api/* is proxied. Must be the Django backend's address.
  const apiTarget = env.API_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    server: {
      allowedHosts,
      proxy: {
        // changeOrigin: false (the default for this object form, spelled out here since
        // the shorthand string form implies changeOrigin: true) preserves the browser's
        // original Host header so it keeps matching the Origin header on the way to the
        // backend - otherwise Django's CSRF check rejects every request, regardless of
        // which LAN device it came from.
        '/api': { target: apiTarget, changeOrigin: false },
      },
    },
  }
})
