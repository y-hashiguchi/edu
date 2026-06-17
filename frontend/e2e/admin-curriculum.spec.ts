import { test, expect } from '@playwright/test';

import {
  E2E_COURSE,
  deleteAiDrivenDevPhase1Task4,
  deletePhase1Task4IfPresent,
  deletePhase5IfPresent,
  login,
  logout,
  openAiDrivenDevCurriculumEdit,
  promoteAdminViaScript,
  registerLearner,
  resetAiDrivenDevCurriculumBaseline,
} from './helpers';

test.describe('admin curriculum editing', () => {
  test.afterAll(async ({ browser }) => {
    const page = await browser.newPage();
    const adminEmail = `cleanup-${Date.now()}@example.com`;
    try {
      await registerLearner(page, adminEmail, 'Cleanup Admin');
      promoteAdminViaScript(adminEmail);
      await login(page, adminEmail);
      await resetAiDrivenDevCurriculumBaseline(page);
    } finally {
      await page.close();
    }
  });

  test('admin edits title and publish reflects on learner view', async ({
    page,
  }) => {
    const adminEmail = `admin-${Date.now()}@example.com`;
    const learnerEmail = `learner-${Date.now()}@example.com`;

    await registerLearner(page, adminEmail, 'Admin');
    promoteAdminViaScript(adminEmail);

    await login(page, adminEmail);
    await openAiDrivenDevCurriculumEdit(page);

    const phase1 = page.locator('[data-test="phase-edit-1"]');
    const titleInput = phase1.locator('input').first();
    await titleInput.fill('編集後タイトル');
    await page.waitForTimeout(800);

    const pending = page.locator('[data-test="pending-count"]');
    await expect(pending).toContainText('1');
    await page.locator('[data-test="publish-button"]').click();
    await page.locator('[data-test="publish-confirm"]').click();
    await expect(page.locator('[data-test="message"]')).toContainText('公開完了');

    await page.getByRole('button', { name: 'ログアウト' }).click();
    await registerLearner(page, learnerEmail, 'Learner');
    await login(page, learnerEmail);
    await page.waitForURL(new RegExp(`/courses/${E2E_COURSE}`));

    await expect(page.getByRole('heading', { name: '編集後タイトル' })).toBeVisible();
  });

  test('admin adds task visible to learner then deletes it', async ({
    page,
  }) => {
    test.setTimeout(180_000);

    const adminEmail = `admin-${Date.now()}@example.com`;
    const learnerEmail = `learner-${Date.now()}@example.com`;

    await registerLearner(page, adminEmail, 'Admin');
    promoteAdminViaScript(adminEmail);
    await login(page, adminEmail);

    await deletePhase1Task4IfPresent(page);

    const phase1 = page.locator('[data-test="phase-edit-1"]');
    await expect(phase1.locator('[data-test^="task-edit-"]')).toHaveCount(3);
    await Promise.all([
      page.waitForResponse(
        (resp) =>
          resp.request().method() === 'POST'
          && resp.url().includes('/phases/1/tasks')
          && !resp.url().includes('/move')
          && resp.status() === 201,
        { timeout: 15_000 },
      ),
      phase1.locator('[data-test="add-task-btn"]').click(),
    ]);
    await expect(phase1.locator('[data-test="task-edit-4"]')).toBeVisible({
      timeout: 15_000,
    });

    await page.getByRole('button', { name: 'ログアウト' }).click();
    await registerLearner(page, learnerEmail, 'Learner');
    await login(page, learnerEmail);
    await page.goto(`/courses/${E2E_COURSE}/phases/1`, {
      waitUntil: 'domcontentloaded',
    });
    await expect(page.locator('[data-test="task-card-4"]')).toBeVisible({
      timeout: 15_000,
    });

    await logout(page);
    await login(page, adminEmail);
    await openAiDrivenDevCurriculumEdit(page);
    await deleteAiDrivenDevPhase1Task4(page);
  });

  test('admin creates and deletes a course from list', async ({ page }) => {
    const adminEmail = `admin-${Date.now()}@example.com`;
    const slug = `e2e-course-${Date.now()}`;
    const title = 'E2E テストコース';

    await registerLearner(page, adminEmail, 'Admin');
    promoteAdminViaScript(adminEmail);
    await login(page, adminEmail);

    await page.goto('/admin/curriculum', { waitUntil: 'domcontentloaded' });
    await page.locator('[data-test="create-course-btn"]').click();
    await expect(page.locator('[data-test="create-course-form"]')).toBeVisible();

    await page.locator('[data-test="create-course-slug"]').fill(slug);
    await page.locator('[data-test="create-course-title"]').fill(title);

    const createDone = page.waitForResponse(
      (resp) =>
        resp.request().method() === 'POST'
        && resp.url().includes('/api/admin/curriculum/courses')
        && resp.status() === 201,
      { timeout: 15_000 },
    );
    await page.locator('[data-test="create-course-submit"]').click();
    await createDone;

    await expect(page.getByRole('link', { name: title })).toBeVisible({
      timeout: 15_000,
    });

    page.once('dialog', (dialog) => void dialog.accept());
    const deleteDone = page.waitForResponse(
      (resp) =>
        resp.request().method() === 'DELETE'
        && resp.url().includes(`/api/admin/curriculum/courses/${slug}`)
        && resp.status() === 204,
      { timeout: 15_000 },
    );
    await page.locator(`[data-test="delete-course-${slug}"]`).click();
    await deleteDone;
    await page.reload({ waitUntil: 'domcontentloaded' });

    await expect(page.locator(`[data-test="delete-course-${slug}"]`)).toHaveCount(0, {
      timeout: 15_000,
    });
    await expect(page.getByRole('link', { name: title })).toHaveCount(0);
  });

  test('admin adds and deletes a phase', async ({ page }) => {
    const adminEmail = `admin-${Date.now()}@example.com`;

    await registerLearner(page, adminEmail, 'Admin');
    promoteAdminViaScript(adminEmail);
    await login(page, adminEmail);

    await deletePhase5IfPresent(page);

    await openAiDrivenDevCurriculumEdit(page);
    await expect(page.locator('[data-test^="phase-edit-"]')).toHaveCount(4);

    const addDone = page.waitForResponse(
      (resp) =>
        resp.request().method() === 'POST'
        && resp.url().includes('/phases')
        && !resp.url().includes('/tasks')
        && resp.status() === 201,
      { timeout: 15_000 },
    );
    await page.locator('[data-test="add-phase-btn"]').click();
    await addDone;

    await expect(page.locator('[data-test="phase-edit-5"]')).toBeVisible({
      timeout: 15_000,
    });

    page.once('dialog', (dialog) => void dialog.accept());
    const deleteDone = page.waitForResponse(
      (resp) =>
        resp.request().method() === 'DELETE'
        && resp.url().includes('/phases/5')
        && resp.status() === 204,
      { timeout: 15_000 },
    );
    await page.locator('[data-test="phase-delete-5"]').click();
    await deleteDone;
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.locator('[data-test="phase-edit-5"]')).toHaveCount(0, {
      timeout: 15_000,
    });
  });
});
