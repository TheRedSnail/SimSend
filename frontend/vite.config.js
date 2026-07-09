import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Ports are configurable via the repo-root .env (or shell environment):
  // FRONTEND_PORT for the dev server, FLASK_PORT for the backend that the
  // /api proxy targets. Defaults: 3000 / 5001.
  const envDir = fileURLToPath(new URL('..', import.meta.url))
  const env = { ...loadEnv(mode, envDir, ''), ...process.env }
  const frontendPort = Number(env.FRONTEND_PORT) || 3000
  const backendPort = Number(env.FLASK_PORT) || 5001

  return {
    plugins: [vue()],
    server: {
      port: frontendPort,
      open: true,
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
