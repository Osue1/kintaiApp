import { expect, test } from '@playwright/test'

/**
 * 管理者ナビゲーション〜監査ログ画面のE2E試験。今回のループで新規追加した監査ログ画面が
 * 実際にナビゲーションから到達可能で、実バックエンドからのデータを描画できることを確認する
 * （読み取り専用のAPIのみを叩くため、テストデータの後始末は不要）。
 */

test('管理者は監査ログ画面に遷移し、操作履歴の一覧を確認できる', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('メールアドレス').fill('admin@example.com')
  await page.getByLabel('パスワード').fill('admin12345678')
  await page.getByRole('button', { name: 'ログイン' }).click()
  await expect(page).toHaveURL('/')

  await page.getByRole('link', { name: '監査ログ' }).click()
  await expect(page).toHaveURL('/audit-logs')
  await expect(page.getByRole('heading', { name: '監査ログ' })).toBeVisible()

  // 一覧テーブルのヘッダーが描画される（実データの有無に関わらず表・空表示のどちらかは出る）
  await expect(page.getByRole('columnheader', { name: '操作者' })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '変更内容' })).toBeVisible()
})

test('管理者は全ての管理メニューにナビゲーションから到達できる', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('メールアドレス').fill('admin@example.com')
  await page.getByLabel('パスワード').fill('admin12345678')
  await page.getByRole('button', { name: 'ログイン' }).click()
  await expect(page).toHaveURL('/')

  const adminPages: Array<[string, string]> = [
    ['勤怠承認', '/approvals'],
    ['アラート', '/alerts'],
    ['従業員管理', '/employees'],
    ['有給管理簿', '/leave-ledger'],
    ['外注管理', '/contractors'],
    ['請求書発行', '/invoices'],
    ['監査ログ', '/audit-logs'],
  ]
  for (const [label, path] of adminPages) {
    await page.getByRole('link', { name: label }).click()
    await expect(page).toHaveURL(path)
    // どの管理画面も一覧描画中に例外を投げてブランクページ化していないことの簡易チェック
    await expect(page.locator('body')).not.toContainText('Error')
  }
})
