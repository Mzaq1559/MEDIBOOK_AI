import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  const backendTarget = env.VITE_PROXY_BACKEND || 'http://localhost:8000'
  const aiServiceTarget = env.VITE_PROXY_AI_SERVICE || 'http://localhost:8001'

  const proxy = {
    '/api': {
      target: backendTarget,
      changeOrigin: true,
    },
    '/chat': {
      target: aiServiceTarget,
      changeOrigin: true,
      rewrite: (path: string) => path.replace(/^\/chat/, '/api/chat'),
    },
  }

  return {
    plugins: [react()],
    server: {
      port: 3000,
      host: '0.0.0.0',
      proxy,
    },
    preview: {
      port: 3000,
      host: '0.0.0.0',
      proxy,
    },
  }
})
