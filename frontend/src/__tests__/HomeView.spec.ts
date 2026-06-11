import { beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { createMemoryHistory, createRouter } from 'vue-router';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: {
      ...actual.api,
      getMyDashboard: vi.fn(),
      listPhases: vi.fn().mockResolvedValue([]),
      listProgress: vi.fn().mockResolvedValue([]),
    },
  };
});

import { api } from '@/lib/api';
import HomeView from '@/views/HomeView.vue';

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

function buildRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/courses/:courseSlug',
        name: 'course-home',
        component: HomeView,
        props: (route) => ({ courseSlug: String(route.params.courseSlug) }),
      },
      {
        path: '/courses/:courseSlug/phases/:phase',
        name: 'course-phase',
        component: { template: '<div>phase</div>' },
      },
    ],
  });
}

const FAKE_DASH = {
  progress_summary: {
    completed_tasks: 0, total_tasks: 12,
    submission_count: 0, average_score: null,
  },
  weakness: { has_enough_data: false, top_weaknesses: [] },
  recommendations: { items: [] },
  nudge: {
    body: 'まずは Phase 1 から。',
    generated_at: '2026-06-08T07:00:00Z',
    is_fresh: true,
  },
};

describe('HomeView (ダッシュボード化)', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('fetches and renders dashboard on mount', async () => {
    mocked.getMyDashboard.mockResolvedValue(FAKE_DASH);
    const router = buildRouter();
    const w = mount(HomeView, {
      props: { courseSlug: 'ai-driven-dev' },
      global: { plugins: [router] },
    });
    await flushPromises();
    expect(mocked.getMyDashboard).toHaveBeenCalledWith('ai-driven-dev');
    expect(w.text()).toContain('まずは Phase 1');
  });

  it('keeps the phase list section below the dashboard', async () => {
    mocked.getMyDashboard.mockResolvedValue(FAKE_DASH);
    const router = buildRouter();
    const w = mount(HomeView, {
      props: { courseSlug: 'ai-driven-dev' },
      global: { plugins: [router] },
    });
    await flushPromises();
    // 既存のフェーズグリッド表記 (PhaseCard.vue が読み込まれる枠) は残る
    expect(w.text()).toMatch(/フェーズ|Phase \d/i);
  });
});
