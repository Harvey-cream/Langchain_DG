import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    minify: 'esbuild',
    // 低配服务器构建时跳过 gzip 体积统计，加快出包
    reportCompressedSize: false,
    chunkSizeWarningLimit: 1200,
    cssMinify: true,
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8010',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            const ct = proxyRes.headers['content-type'] as string | undefined;
            if (ct?.includes('text/event-stream')) {
              proxyRes.headers['x-accel-buffering'] = 'no';
            }
          });
        },
      },
      '/media': {
        target: 'http://localhost:8010',
        changeOrigin: true,
      },
    },
  }
})