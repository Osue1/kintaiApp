import { expect, test } from '@playwright/test'

/**
 * ログインフローのE2E試験。実ブラウザから実バックエンド（Django + PostgreSQL）へ
 * セッションCookie + CSRFで認証する一連の流れを、モックなしで検証する。
 *
 * 認証情報は create_demo_data コマンドで投入されるデモアカウントを使う
 * （backend/apps/common/management/commands/create_demo_data.py 参照）。
 */

test('従業員でログインするとマイページへ遷移し、ナビゲーションが表示される', async ({ page }) => {
  await page.goto('/login')

  await page.getByLabel('メールアドレス').fill('sato@example.com')
  await page.getByLabel('パスワード').fill('employee12345')
  await page.getByRole('button', { name: 'ログイン' }).click()

  await expect(page).toHaveURL('/')
  // 打刻状態（出勤する/退勤する）は実データの状況に左右されるため、状態に依存しない
  // ナビゲーション項目の表示で「ログインしてマイページに到達できたこと」を確認する。
  await expect(page.getByRole('link', { name: 'マイページ' })).toBeVisible()
  await expect(page.getByRole('link', { name: '休暇申請' })).toBeVisible()
  // 一般従業員には管理者専用ナビが出ないこと
  await expect(page.getByRole('link', { name: '監査ログ' })).not.toBeVisible()
})

test('存在しないメールアドレスでログインするとエラーメッセージが表示される', async ({ page }) => {
  // 実在するデモアカウントに対して誤ったパスワードを繰り返し送ると、django-axesの
  // ログイン失敗回数制限（5回でロック、設計書 第3.1章）に本当に抵触してしまい、
  // デモアカウント自体が一定時間ログインできなくなる。存在しないメールアドレスなら
  // そのリスクなしに同じエラー文言を確認できる。
  await page.goto('/login')

  await page.getByLabel('メールアドレス').fill('does-not-exist@example.com')
  await page.getByLabel('パスワード').fill('whatever-password-123')
  await page.getByRole('button', { name: 'ログイン' }).click()

  await expect(page.getByText('メールアドレスまたはパスワードが違います。')).toBeVisible()
  await expect(page).toHaveURL('/login')
})

test('未ログインで保護ページへ直接アクセスするとログイン画面へリダイレクトされる', async ({ page }) => {
  await page.goto('/employees')
  await expect(page).toHaveURL(/\/login/)
})
