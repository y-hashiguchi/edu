import { test, expect } from '@playwright/test';

// CI に admin 昇格手順がないため、現状は skip。
// ローカル実行では promote_admin スクリプトで is_admin を付けてから
// `test.describe.skip` を `test.describe` に切り替えて検証する。
test.describe.skip('admin curriculum editing', () => {
  test('admin edits title and publish reflects on learner view', async ({ page }) => {
    const adminEmail = `admin-${Date.now()}@example.com`;
    const learnerEmail = `learner-${Date.now()}@example.com`;

    // 1) 管理者を作成（admin 昇格は別途 backend スクリプトで実行する想定）。
    await page.goto('/login');
    await page.getByRole('tab', { name: '新規登録' }).click();
    await page.getByLabel('メールアドレス').fill(adminEmail);
    await page.getByLabel('お名前').fill('Admin');
    await page.locator('[data-test="course-select"]').selectOption('ai-driven-dev');
    await page.getByLabel('パスワード').fill('password12345');
    await page.getByRole('button', { name: '登録する' }).click();
    await expect(page.getByText('登録できました')).toBeVisible();

    // 2) admin ログイン → カリキュラム編集へ。
    await page.getByLabel('パスワード').fill('password12345');
    await page.getByRole('button', { name: 'ログイン' }).click();
    await page.goto('/admin/curriculum');
    await page.getByText('AI駆動開発').click();
    await page.waitForURL(/\/admin\/curriculum\/ai-driven-dev/);

    // 3) Phase 1 の title を編集。
    const phase1 = page.locator('[data-test="phase-edit-1"]');
    const titleInput = phase1.locator('input').first();
    await titleInput.fill('編集後タイトル');
    // debounce flush
    await page.waitForTimeout(800);

    // 4) ドラフト件数増、公開ボタン押下。
    const pending = page.locator('[data-test="pending-count"]');
    await expect(pending).toContainText('1');
    await page.locator('[data-test="publish-button"]').click();
    await page.locator('[data-test="publish-confirm"]').click();
    await expect(page.locator('[data-test="message"]')).toContainText('公開完了');

    // 5) 学習者として確認。
    await page.locator('text=ログアウト').click();
    await page.goto('/login');
    await page.getByRole('tab', { name: '新規登録' }).click();
    await page.getByLabel('メールアドレス').fill(learnerEmail);
    await page.getByLabel('お名前').fill('Learner');
    await page.locator('[data-test="course-select"]').selectOption('ai-driven-dev');
    await page.getByLabel('パスワード').fill('password12345');
    await page.getByRole('button', { name: '登録する' }).click();
    await page.getByLabel('パスワード').fill('password12345');
    await page.getByRole('button', { name: 'ログイン' }).click();
    await page.waitForURL(/\/courses\/ai-driven-dev/);

    await expect(page.getByText('編集後タイトル')).toBeVisible();
  });
});
