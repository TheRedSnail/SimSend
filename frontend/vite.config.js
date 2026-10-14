import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Configurable via the repo-root .env (or shell environment):
  // FRONTEND_PORT for the dev server, FLASK_PORT for the backend that the
  // /api proxy targets (defaults 3000 / 5001). FRONTEND_HOST controls the
  // bind address; it defaults to localhost so the dev server and its
  // unauthenticated /api proxy aren't exposed to the LAN (set 0.0.0.0 to
  // opt in). FRONTEND_OPEN=false stops it opening a browser (CI, Docker).
  const envDir = fileURLToPath(new URL('..', import.meta.url))
  const env = { ...loadEnv(mode, envDir, ''), ...process.env }
  const frontendPort = Number(env.FRONTEND_PORT) || 3000
  const backendPort = Number(env.FLASK_PORT) || 5001
  const frontendHost = env.FRONTEND_HOST || 'localhost'
  const openBrowser = env.FRONTEND_OPEN !== 'false' && !env.CI

  return {
    plugins: [vue()],
    server: {
      host: frontendHost,
      port: frontendPort,
      open: openBrowser,
      proxy: {
        '/api': {
          target: `http://localhost:${backendPort}`,
          changeOrigin: true,
          secure: false
        }
      }
    }
  }
})
