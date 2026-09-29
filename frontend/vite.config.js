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
  // 公開中の radio.wawa-app.me はサブパス維持のため base は '/Midair.io/'
  // （ルート直下配信にする場合は BASE_PATH を指定しない＝既定の '/'）
  base: process.env.BASE_PATH || '/',
  define: {
    // Vite dev / 通常ビルドでは false（APIは相対 /api、履歴ルーティング）
    __STANDALONE__: 'false',
    __VUE_OPTIONS_API__: 'true',
    __VUE_PROD_DEVTOOLS__: 'false',
    __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: 'false',
  },
  build: {
    // 遅延読み込み（ルート分割）で初回JSを小さくする。
    // modulepreload のポリフィルは古いブラウザ向けのため無効化
    // （対応ブラウザでは元から不要。ついでに成果物も少し小さくなる）
    modulePreload: { polyfill: false },
    rollupOptions: {
      output: {
        // ベンダー（Vue本体）とアプリを分けてキャッシュ効率を上げる
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia'],
        },
      },
    },
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
