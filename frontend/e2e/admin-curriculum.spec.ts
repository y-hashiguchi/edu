import { test, expect, type Page } from '@playwright/test';

import {
  E2E_COURSE,
  login,
  logout,
  promoteAdminViaScript,
  registerLearner,
} from './helpers';

async function openCurriculumEdit(page: Page): Promise<void> {
  await page.goto('/admin/curriculum/ai-driven-dev', {
    waitUntil: 'domcontentloaded',
  });
  await expect(page.locator('[data-test="admin-curriculum-edit-view"]')).toBeVisible({
    timeout: 15_000,
  });
}

/** Prior failed runs may leave Phase 1 task 4 behind; remove before asserting counts. */
async function deletePhase1Task4IfPresent(page: Page): Promise<void> {
  await openCurriculumEdit(page);
  const task4 = page.locator('[data-test="task-edit-4"]');
  if ((await task4.count()) === 0) return;
  await deleteTask4(page);
}

async function deleteTask4(page: Page): Promise<void> {
  const task4 = page.locator('[data-test="task-edit-4"]');
  await task4.scrollIntoViewIfNeeded();
  const deleteBtn = task4.locator('[data-test="task-delete"]');
  await Promise.all([
    page.waitForResponse(
      (resp) =>
        resp.request().method() === 'DELETE'
        && resp.url().includes('/phases/1/tasks/4')
        && resp.status() === 204,
      { timeout: 15_000 },
    ),
    (async () => {
      page.once('dialog', (dialog) => void dialog.accept());
      await deleteBtn.click();
    })(),
  ]);
  await expect(task4).toHaveCount(0, { timeout: 15_000 });
}

test.describe('admin curriculum editing', () => {
  test('admin edits title and publish reflects on learner view', async ({
    page,
  }) => {
    const adminEmail = `admin-${Date.now()}@example.com`;
    const learnerEmail = `learner-${Date.now()}@example.com`;

    await registerLearner(page, adminEmail, 'Admin');
    promoteAdminViaScript(adminEmail);

    await login(page, adminEmail);
    await openCurriculumEdit(page);

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
    await openCurriculumEdit(page);
    await deleteTask4(page);
    await expect(
      page.locator('[data-test="phase-edit-1"]').locator('[data-test^="task-edit-"]'),
    ).toHaveCount(3, { timeout: 15_000 });
  });
});
