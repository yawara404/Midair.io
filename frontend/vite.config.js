import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Google Analytics の測定IDを index.html に埋め込む。
// （Vite の %VITE_*% 置換は「変数が未定義だとプレースホルダのまま残る」ため、
//   未設定時に空文字へ置き換えて GA を読み込まないようにする）
function gaIdPlugin() {
  return {
    name: 'midair-ga-id',
    transformIndexHtml(html) {
      const gaId = process.env.VITE_GA_ID || ''
      return html.replaceAll('%VITE_GA_ID%', gaId)
    },
  }
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue(), gaIdPlugin()],
  // サブパス配信（例: /Midair.io/）に対応。`BASE_PATH` 未設定なら '/'
  base: process.env.BASE_PATH || '/',
  define: {
    // Vite dev / 通常ビルドでは false（APIは相対 /api、履歴ルーティング）
    __STANDALONE__: 'false',
    __VUE_OPTIONS_API__: 'true',
    __VUE_PROD_DEVTOOLS__: 'false',
    __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: 'false',
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
