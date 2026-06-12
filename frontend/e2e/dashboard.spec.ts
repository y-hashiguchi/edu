import { test, expect } from '@playwright/test';

/**
 * Dashboard golden path:
 *   register → login → submit 3 tasks (2 with weak markers, 1 OK) →
 *   verify dashboard cards reflect the activity.
 *
 * Requires the backend to run with CLAUDE_STUB_MODE=true so grading is
 * deterministic. Score profile:
 *   - "stub:weak"  → 55  (drives weakness analysis)
 *   - "stub:ok"    → 75
 *   - "stub:great" → 92
 */

const COURSE = 'ai-driven-dev';
const PASSWORD = 'password12345';

async function register(page: import('@playwright/test').Page, email: string) {
  await page.goto('/login');
  await page.getByRole('tab', { name: '新規登録' }).click();
  await page.getByLabel('メールアドレス').fill(email);
  await page.getByLabel('お名前').fill('Dashboard E2E 学習者');
  await page.locator('[data-test="course-select"]').waitFor();
  await page.locator('[data-test="course-select"]').selectOption(COURSE);
  await page.getByLabel('パスワード').fill(PASSWORD);
  await page.getByRole('button', { name: '登録する' }).click();
  await expect(page.getByText('登録できました')).toBeVisible();
}

async function login(page: import('@playwright/test').Page, email: string) {
  await page.getByLabel('パスワード').fill(PASSWORD);
  await page.getByRole('button', { name: 'ログイン' }).click();
  await page.waitForURL(new RegExp(`/courses/${COURSE}`));
}

async function submitTask(
  page: import('@playwright/test').Page,
  taskNo: number,
  marker: 'weak' | 'ok' | 'great',
  expectedScore: number,
) {
  const card = page.locator(`[data-test="task-card-${taskNo}"]`);
  await card.scrollIntoViewIfNeeded();
  await card
    .locator('textarea')
    .fill(`E2E task ${taskNo} stub:${marker}`);
  await card.getByRole('button', { name: /^提出する|再提出する$/ }).click();
  // The score badge replaces the placeholder text once grading completes
  // (sync mode in CI / local; CLAUDE_STUB_MODE returns instantly).
  await expect(card.locator('.badge')).toContainText(String(expectedScore), {
    timeout: 30_000,
  });
}

test('dashboard reflects three graded submissions', async ({ page }) => {
  const email = `dash-${Date.now()}@example.com`;

  await register(page, email);
  await login(page, email);

  // Phase 1 has 3 tasks in ai-driven-dev (Git, VSCode 拡張, curl REST API).
  await page.goto(`/courses/${COURSE}/phases/1`);
  await submitTask(page, 1, 'weak', 55);
  await submitTask(page, 2, 'weak', 55);
  await submitTask(page, 3, 'ok', 75);

  // Navigate back to the course home (= dashboard surface).
  await page.goto(`/courses/${COURSE}`);

  // Progress summary: 3 / 12 tasks (ai-driven-dev = 4 phases × 3 tasks).
  const progress = page.locator('section.progress-summary');
  await expect(progress).toBeVisible();
  await expect(progress.locator('.num')).toContainText('3 / 12');

  // Weakness card: with 3 submissions Sprint 5's MIN_SUBMISSION_THRESHOLD
  // is met. ai-driven-dev Phase 1 tasks each carry a distinct skill_tag,
  // so MIN_TAG_SUBMISSIONS=2 may yield no qualifying tag — in that case
  // the card renders the "提出をもう少し" empty body. Either branch is
  // acceptable here; we just verify the card is mounted with its heading.
  const weakness = page.locator('section.weakness');
  await expect(weakness).toBeVisible();
  await expect(
    weakness.getByRole('heading', { name: 'もう一押しの分野' }),
  ).toBeVisible();

  // Recommendations card may or may not have items depending on whether
  // curriculum embeddings have been seeded in this environment. We only
  // assert the section header so the spec is robust in a fresh dev DB.
  await expect(
    page.getByRole('heading', { name: '次のおすすめ' }),
  ).toBeVisible();

  // Nudge banner: stub returns canned coaching text on the nudge model.
  await expect(page.locator('section.nudge-banner')).toBeVisible();
});

test('resubmitting a task updates the badge with the new score', async ({
  page,
}) => {
  const email = `resubmit-${Date.now()}@example.com`;

  await register(page, email);
  await login(page, email);

  await page.goto(`/courses/${COURSE}/phases/1`);
  await submitTask(page, 1, 'weak', 55);

  // Re-submit Task 1 with a "great" marker. The score badge must flip
  // from 55 to 92, proving the upsert + regrade-on-resubmit cycle.
  const card = page.locator('[data-test="task-card-1"]');
  await card.locator('textarea').fill('E2E task 1 stub:great');
  await card.getByRole('button', { name: '再提出する' }).click();
  await expect(card.locator('.badge')).toContainText('92', { timeout: 30_000 });

  // The regrade BUTTON cycle (compared with the resubmit cycle above)
  // is covered by `backend/tests/test_async_regrade.py` and the
  // curriculum store unit tests — exercising it in E2E would require
  // either disabling the frontend's UX-side 60 s cooldown or sleeping
  // the test for a minute. Neither is worth it: the request/response
  // is identical to the resubmit path the worker already runs.
});
