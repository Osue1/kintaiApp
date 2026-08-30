import { fileURLToPath, URL } from 'node:url'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig(({ command }) => ({
  plugins: [vue()],
  // ビルド成果物はDjangoのSTATIC_URL配下（/static/）にそのまま同梱配信する
  // 構成があるため、build時だけアセットの参照先を/static/にする。
  // 開発サーバー自体を/static/配下に持ち上げると server.proxy の '/static'
  // ルール（バックエンドのDjango管理画面用静的ファイル）と衝突するため、
  // dev時は従来通りルート'/'のまま。
  base: command === 'build' ? '/static/' : '/',
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    host: true,
    port: 5173,
    // 開発中も同一オリジンに見せる。セッションCookieとCSRFがそのまま通る
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: false },
      '/admin': { target: 'http://localhost:8000', changeOrigin: false },
      '/static': { target: 'http://localhost:8000', changeOrigin: false },
    },
  },
  test: {
    environment: 'jsdom',
    // e2e/ 配下は Playwright 専用（playwright.config.ts）。vitestの既定globは
    // *.test.ts / *.spec.ts にマッチするため、拡張子を e2e.ts にして自然に住み分けている
    // が、念のため明示的にも除外しておく。exclude を指定するとvitestの既定リストを
    // 丸ごと上書きしてしまう仕様のため、既定値（dist/.git等）をそのまま含めた上で
    // e2e/ を追加している。
    exclude: [
      '**/node_modules/**',
      '**/dist/**',
      '**/cypress/**',
      '**/.{idea,git,cache,output,temp}/**',
      '**/{karma,rollup,webpack,vite,vitest,jest,ava,babel,nyc,cypress,tsup,build}.config.*',
      '**/e2e/**',
    ],
  },
}))
