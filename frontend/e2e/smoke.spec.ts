import { test, expect } from '@playwright/test';

test('login page renders', async ({ page }) => {
  await page.goto('/login');
  await expect(page.getByRole('tab', { name: 'ログイン' })).toBeVisible();
  await expect(page.getByLabel('メールアドレス')).toBeVisible();
  await expect(page.getByLabel('パスワード')).toBeVisible();
});

test('register and login reaches course home', async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;

  await page.goto('/login');
  await page.getByRole('tab', { name: '新規登録' }).click();

  await page.getByLabel('メールアドレス').fill(email);
  await page.getByLabel('お名前').fill('E2E 学習者');
  await page.locator('[data-test="course-select"]').waitFor();
  await page.locator('[data-test="course-select"]').selectOption('ai-driven-dev');
  await page.getByLabel('パスワード').fill('password12345');
  await page.getByRole('button', { name: '登録する' }).click();

  await expect(page.getByText('登録できました')).toBeVisible();

  await page.getByLabel('パスワード').fill('password12345');
  await page.getByRole('button', { name: 'ログイン' }).click();

  await page.waitForURL(/\/courses\/ai-driven-dev/);
  // 「あなたの進捗」 appears in both the section heading (h2) and the
  // progress-summary paragraph. Pin to the heading so the assertion
  // is unambiguous even when both are mounted.
  await expect(
    page.getByRole('heading', { name: 'あなたの進捗' }),
  ).toBeVisible();
});
