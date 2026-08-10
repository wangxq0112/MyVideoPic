import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发期把 /api 代理到 Django，使前端始终以同源方式请求。
// 这样 dev 与 Nginx 部署下的请求路径完全一致，也不再依赖 CORS。
// 样式为手写 CSS（design token + 语义类），不引入任何构建期 CSS 框架，
// 保证 clone 下来只装 4 个运行时依赖就能跑。
const DJANGO_TARGET = process.env.MYVIDEOPIC_API || 'http://127.0.0.1:8000'

// 视频流是长连接，去掉超时避免大文件播放中途被切断
const API_PROXY = {
  '/api': {
    target: DJANGO_TARGET,
    changeOrigin: true,
    timeout: 0,
    proxyTimeout: 0,
  },
}

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    host: '127.0.0.1',   // 只监听本机，不暴露到局域网
    proxy: API_PROXY,
  },
  // preview 不继承 server.proxy，得单独给一份，
  // 否则「npm run build && npm run preview」这条不装 Nginx 的路子取不到 /api。
  preview: {
    port: 4173,
    host: '127.0.0.1',
    proxy: API_PROXY,
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 900,
  },
})
