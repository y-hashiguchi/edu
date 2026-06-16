import { test, expect } from '@playwright/test';

import { login, logout, promoteAdminViaScript, registerLearner } from './helpers';

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

  test('admin filters cohort summary by enrollment batch label', async ({
    page,
  }) => {
    const ts = Date.now();
    const adminEmail = `cohort-filter-admin-${ts}@example.com`;
    const learnerEmail = `cohort-filter-learner-${ts}@example.com`;
    const batchLabel = `batch-${ts}`;

    await registerLearner(page, adminEmail, 'Filter Admin');
    promoteAdminViaScript(adminEmail);
    await login(page, adminEmail);
    await logout(page);

    // registerLearner leaves the user on /login without a session — no logout needed.
    await registerLearner(page, learnerEmail, 'Filter Learner');

    await login(page, adminEmail);
    await page.goto('/admin/users');
    await page.getByRole('cell', { name: learnerEmail }).click();
    await expect(page.locator('[data-test="course-selector"]')).toBeVisible({
      timeout: 15_000,
    });
    const labelInput = page.locator('[data-test="cohort-label-input"]');
    await labelInput.click();
    await labelInput.fill(batchLabel);
    await expect(labelInput).toHaveValue(batchLabel);
    const patchDone = page.waitForResponse(
      (response) =>
        response.request().method() === 'PATCH' &&
        response.url().includes('/enrollments/ai-driven-dev') &&
        response.ok(),
    );
    await page.locator('[data-test="save-cohort-label"]').click();
    const patchResponse = await patchDone;
    expect((await patchResponse.json()).cohort_label).toBe(batchLabel);

    await page.goto('/admin/cohort');
    await expect(page.locator('[data-test="loading"]')).toBeHidden({
      timeout: 15_000,
    });
    await expect(page.locator('[data-test="cohort-label-select"]')).toBeVisible({
      timeout: 15_000,
    });
    await page.locator('[data-test="cohort-label-select"]').selectOption(batchLabel);
    await expect(page.locator('[data-test="loading"]')).toBeHidden({
      timeout: 15_000,
    });
    await expect(page.locator('[data-test="enrolled-count"] .value')).toHaveText(
      '1',
    );
  });
});
