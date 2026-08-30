import { defineConfig, devices } from '@playwright/test'

/**
 * E2E試験の設定（設計上の欠陥の修正: これまでフロントエンドの「結合試験」はjsdom上での
 * モックAPI検証にとどまり、実ブラウザで実際のバックエンドと通信する試験が存在しなかった）。
 *
 * vitest（単体・画面結合試験）とは別プロセス・別ランナーとして完全に分離している
 * （vite.config.ts の test.exclude を参照）。テストファイルは `e2e/**\/*.e2e.ts` に
 * 限定し、vitestの既定glob（*.test.ts / *.spec.ts）と衝突しない拡張子にしてある。
 *
 * 前提: scripts/local-dev.sh up でバックエンド(:8000)・フロントエンド(:5173)・
 * PostgreSQLが起動していること、および create_demo_data コマンドでデモアカウント
 * （admin@example.com / sato@example.com 等）が投入済みであること。
 */
export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.e2e.ts',
  // 実データ（ローカルのdev用DB）を共有して動くため、複数ワーカーの並列実行や
  // リトライは意図しない状態のもつれを招きうる。1ワーカー・直列・リトライ無しに固定する。
  workers: 1,
  fullyParallel: false,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    // 既に scripts/local-dev.sh up で起動済みならそれをそのまま使う
    // （reuseExistingServer）。起動していなければこのコマンドで一括起動する。
    command: 'cd .. && bash scripts/local-dev.sh up',
    url: 'http://localhost:5173',
    reuseExistingServer: true,
    timeout: 120_000,
  },
})
