import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(here, '..')

/**
 * スタンドアロン（Live Server 用）ビルド。
 *
 * - ソースは frontend/src（SFC）のみ。これを唯一のソースとする。
 * - 出力はリポジトリ直下の assets/app.js（IIFE）と assets/app.css。
 * - Vue も同梱するので CDN に依存しない（Live Server でそのまま動く）。
 * - __STANDALONE__ = true により、ハッシュルーティング /
 *   API・WebSocket は <ホスト>:8000 を直接参照 に切り替わる。
 */
export default defineConfig({
  plugins: [vue()],
  define: {
    __STANDALONE__: 'true',
    __VUE_OPTIONS_API__: 'true',
    __VUE_PROD_DEVTOOLS__: 'false',
    __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: 'false',
    // lib ビルドでは process.env.NODE_ENV が自動定義されないため明示する
    'process.env.NODE_ENV': JSON.stringify('production'),
  },
  build: {
    outDir: resolve(repoRoot, 'assets'),
    emptyOutDir: false,
    cssCodeSplit: false,
    lib: {
      entry: resolve(here, 'src/main.js'),
      name: 'MidairStandalone',
      formats: ['iife'],
      fileName: () => 'app.js',
      cssFileName: 'app',
    },
    rollupOptions: {
      output: { assetFileNames: 'app.[ext]' },
    },
  },
})
