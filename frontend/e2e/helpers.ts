import { execSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { expect, type Page } from '@playwright/test';

const E2E_DIR = path.dirname(fileURLToPath(import.meta.url));
const BACKEND_DIR = path.resolve(E2E_DIR, '../../backend');

export const E2E_PASSWORD = 'password12345';
export const E2E_COURSE = 'ai-driven-dev';

/** Promote a registered user to admin via backend CLI (same DB as running API). */
export function promoteAdminViaScript(email: string): void {
  const databaseUrl =
    process.env.DATABASE_URL ??
    'postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor';

  execSync(`uv run python -m scripts.promote_admin ${JSON.stringify(email)}`, {
    cwd: BACKEND_DIR,
    env: {
      ...process.env,
      DATABASE_URL: databaseUrl,
      ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY ?? 'test-key',
      JWT_SECRET_KEY: process.env.JWT_SECRET_KEY ?? 'test-secret',
    },
    stdio: 'pipe',
  });
}

export async function registerLearner(
  page: Page,
  email: string,
  name: string,
  courseSlug = E2E_COURSE,
): Promise<void> {
  await page.goto('/login');
  await page.getByRole('tab', { name: '新規登録' }).click();
  await page.getByLabel('メールアドレス').fill(email);
  await page.getByLabel('お名前').fill(name);
  await page.locator('[data-test="course-select"]').waitFor();
  await expect(
    page.locator(`[data-test="course-select"] option[value="${courseSlug}"]`),
  ).toHaveCount(1, { timeout: 15_000 });
  await page.locator('[data-test="course-select"]').selectOption(courseSlug);
  await page.getByLabel('パスワード').fill(E2E_PASSWORD);
  await page.getByRole('button', { name: '登録する' }).click();
  await expect(page.getByText('登録できました')).toBeVisible();
}

export async function login(
  page: Page,
  email?: string,
  password = E2E_PASSWORD,
): Promise<void> {
  await page.goto('/login');
  await page.getByRole('tab', { name: 'ログイン' }).click();
  if (email) {
    await page.getByLabel('メールアドレス').fill(email);
  }
  await page.getByLabel('パスワード').fill(password);
  await page.getByRole('button', { name: 'ログイン' }).click();
  await page.waitForURL(/\/courses/, { timeout: 15_000 });
}

export async function logout(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'ログアウト' }).click();
  await page.waitForURL(/\/login/, { timeout: 15_000 });
}

export async function openAiDrivenDevCurriculumEdit(page: Page): Promise<void> {
  await page.goto('/admin/curriculum/ai-driven-dev', {
    waitUntil: 'domcontentloaded',
  });
  await expect(page.locator('[data-test="admin-curriculum-edit-view"]')).toBeVisible({
    timeout: 15_000,
  });
}

/** Remove stray Phase 1 task 4 left by a failed admin curriculum E2E run. */
export async function deletePhase1Task4IfPresent(page: Page): Promise<void> {
  await openAiDrivenDevCurriculumEdit(page);
  const task4 = page.locator('[data-test="task-edit-4"]');
  if ((await task4.count()) === 0) return;
  await deleteAiDrivenDevPhase1Task4(page);
}

export async function deleteAiDrivenDevPhase1Task4(page: Page): Promise<void> {
  const task4 = page.locator('[data-test="task-edit-4"]');
  if ((await task4.count()) === 0) return;
  await task4.scrollIntoViewIfNeeded();
  const deleteBtn = task4.locator('[data-test="task-delete"]');
  page.once('dialog', (dialog) => void dialog.accept());
  const deleteDone = page.waitForResponse(
    (resp) =>
      resp.request().method() === 'DELETE'
      && resp.url().includes('/phases/1/tasks/4')
      && resp.status() === 204,
    { timeout: 15_000 },
  );
  await deleteBtn.click();
  await deleteDone;
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.locator('[data-test="admin-curriculum-edit-view"]')).toBeVisible({
    timeout: 15_000,
  });
  await expect(
    page.locator('[data-test="phase-edit-1"]').locator('[data-test^="task-edit-"]'),
  ).toHaveCount(3, { timeout: 15_000 });
}

/** Remove stray Phase 5 left by a failed admin curriculum E2E run. */
export async function deletePhase5IfPresent(page: Page): Promise<void> {
  await openAiDrivenDevCurriculumEdit(page);
  const phase5 = page.locator('[data-test="phase-edit-5"]');
  if ((await phase5.count()) === 0) return;
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
  await expect(page.locator('[data-test="admin-curriculum-edit-view"]')).toBeVisible({
    timeout: 15_000,
  });
}

/** Restore ai-driven-dev to the seeded 12-task baseline after admin E2E mutations. */
export async function resetAiDrivenDevCurriculumBaseline(page: Page): Promise<void> {
  await deletePhase1Task4IfPresent(page);
  await deletePhase5IfPresent(page);
}
