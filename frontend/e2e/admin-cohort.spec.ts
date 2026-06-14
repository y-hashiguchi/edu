import { test, expect } from '@playwright/test';

import { login, promoteAdminViaScript, registerLearner } from './helpers';

test.describe('admin cohort dashboard', () => {
  test('admin sees cohort summary metrics', async ({ page }) => {
    const adminEmail = `cohort-admin-${Date.now()}@example.com`;

    await registerLearner(page, adminEmail, 'Cohort Admin');
    promoteAdminViaScript(adminEmail);
    await login(page, adminEmail);

    await page.goto('/admin/cohort');
    await expect(page.getByRole('heading', { name: 'コホート集計' })).toBeVisible();
    await expect(page.locator('[data-test="loading"]')).toBeHidden({
      timeout: 15_000,
    });
    await expect(page.locator('[data-test="enrolled-count"]')).toBeVisible();
    await expect(page.locator('[data-test="enrolled-count"] .value')).toBeVisible();
  });
});
