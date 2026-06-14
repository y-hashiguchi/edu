import { test, expect } from '@playwright/test';

import { login, promoteAdminViaScript, registerLearner } from './helpers';

test.describe('admin scheduled broadcast', () => {
  test('admin can schedule a course broadcast', async ({ page }) => {
    const adminEmail = `sched-admin-${Date.now()}@example.com`;

    await registerLearner(page, adminEmail, 'Sched Admin');
    promoteAdminViaScript(adminEmail);
    await login(page, adminEmail);

    await page.goto('/admin/notify');
    await page.locator('[data-test="mode-schedule"]').click();
    await expect(page.locator('[data-test="scheduled-at"]')).not.toHaveValue('');

    const uniqueTitle = `予約テスト-${Date.now()}`;

    await page.locator('[data-test="notify-title"]').fill(uniqueTitle);
    await page.locator('[data-test="notify-body"]').fill('来週のリマインド');

    await page.locator('[data-test="notify-submit"]').click();
    await expect(page.getByText('予約を登録しました')).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.locator('[data-test="scheduled-list"]')).toBeVisible();
    await expect(
      page.locator('[data-test="scheduled-list"] .title', { hasText: uniqueTitle }),
    ).toBeVisible();
  });
});
