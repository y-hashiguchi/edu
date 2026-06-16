import { test, expect } from '@playwright/test';

import {
  E2E_COURSE,
  login,
  promoteAdminViaScript,
  registerLearner,
} from './helpers';

test.describe('admin curriculum editing', () => {
  test('admin edits title and publish reflects on learner view', async ({
    page,
  }) => {
    const adminEmail = `admin-${Date.now()}@example.com`;
    const learnerEmail = `learner-${Date.now()}@example.com`;

    // 1) 管理者ユーザーを登録し CLI で is_admin を付与。
    await registerLearner(page, adminEmail, 'Admin');
    promoteAdminViaScript(adminEmail);

    // 2) admin ログイン → カリキュラム編集へ。
    await login(page, adminEmail);
    await page.goto('/admin/curriculum');
    await expect(page.getByRole('heading', { name: 'カリキュラム編集' })).toBeVisible();
    await page.getByRole('link', { name: /AI駆動型開発 補足/ }).click();
    await page.waitForURL(/\/admin\/curriculum\/ai-driven-dev/);

    // 3) Phase 1 の title を編集。
    const phase1 = page.locator('[data-test="phase-edit-1"]');
    const titleInput = phase1.locator('input').first();
    await titleInput.fill('編集後タイトル');
    // debounce flush (500ms) + margin
    await page.waitForTimeout(800);

    // 4) ドラフト件数増、公開ボタン押下。
    const pending = page.locator('[data-test="pending-count"]');
    await expect(pending).toContainText('1');
    await page.locator('[data-test="publish-button"]').click();
    await page.locator('[data-test="publish-confirm"]').click();
    await expect(page.locator('[data-test="message"]')).toContainText('公開完了');

    // 5) 学習者として確認。
    await page.getByRole('button', { name: 'ログアウト' }).click();
    await registerLearner(page, learnerEmail, 'Learner');
    await login(page, learnerEmail);
    await page.waitForURL(new RegExp(`/courses/${E2E_COURSE}`));

    await expect(page.getByRole('heading', { name: '編集後タイトル' })).toBeVisible();
  });

  test('admin adds task visible to learner then deletes it', async ({
    page,
  }) => {
    const adminEmail = `admin-${Date.now()}@example.com`;
    const learnerEmail = `learner-${Date.now()}@example.com`;

    await registerLearner(page, adminEmail, 'Admin');
    promoteAdminViaScript(adminEmail);
    await login(page, adminEmail);

    await page.goto('/admin/curriculum');
    await page.getByRole('link', { name: /AI駆動型開発 補足/ }).click();
    await page.waitForURL(/\/admin\/curriculum\/ai-driven-dev/);

    const phase1 = page.locator('[data-test="phase-edit-1"]');
    await expect(phase1.locator('[data-test^="task-edit-"]')).toHaveCount(3);
    await phase1.locator('[data-test="add-task-btn"]').click();
    await expect(phase1.locator('[data-test="task-edit-4"]')).toBeVisible({
      timeout: 10_000,
    });

    await page.getByRole('button', { name: 'ログアウト' }).click();
    await registerLearner(page, learnerEmail, 'Learner');
    await login(page, learnerEmail);
    await page.goto(`/courses/${E2E_COURSE}/phases/1`);
    await expect(page.locator('[data-test="task-card-4"]')).toBeVisible({
      timeout: 15_000,
    });

    await logout(page);
    await login(page, adminEmail);
    await page.goto('/admin/curriculum/ai-driven-dev');
    page.once('dialog', (dialog) => dialog.accept());
    await page
      .locator('[data-test="task-edit-4"]')
      .locator('[data-test="task-delete"]')
      .click();
    await expect(
      page.locator('[data-test="phase-edit-1"]').locator('[data-test^="task-edit-"]'),
    ).toHaveCount(3, { timeout: 10_000 });
  });
});
