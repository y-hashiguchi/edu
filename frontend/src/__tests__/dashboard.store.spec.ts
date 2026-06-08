import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: { ...actual.api, getMyDashboard: vi.fn() },
  };
});

import { api } from '@/lib/api';
import { useDashboardStore } from '@/stores/dashboard';

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

const FAKE = {
  progress_summary: {
    completed_tasks: 5, total_tasks: 12,
    submission_count: 5, average_score: 70.0,
  },
  weakness: {
    has_enough_data: true,
    top_weaknesses: [
      { tag: 'AI協調', average_score: 60.0, submission_count: 3 },
    ],
  },
  recommendations: {
    items: [{
      phase: 2, task_no: 1, title: 't',
      skill_tags: ['AI協調'], match_tag: 'AI協調', rag_score: 0.8,
    }],
  },
  nudge: {
    body: '次は Phase 2 task 1 をやろう。',
    generated_at: '2026-06-08T07:00:00Z',
    is_fresh: true,
  },
};

describe('dashboard store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('fetch populates data on success', async () => {
    mocked.getMyDashboard.mockResolvedValue(FAKE);
    const store = useDashboardStore();
    await store.fetch();
    expect(store.data?.nudge.is_fresh).toBe(true);
    expect(store.error).toBeNull();
    expect(store.loading).toBe(false);
  });

  it('fetch sets error message and clears loading on failure', async () => {
    mocked.getMyDashboard.mockRejectedValue(new Error('network'));
    const store = useDashboardStore();
    await store.fetch();
    expect(store.data).toBeNull();
    expect(store.error).toBe('読み込みに失敗しました');
    expect(store.loading).toBe(false);
  });

  it('invalidate clears cached data', async () => {
    mocked.getMyDashboard.mockResolvedValue(FAKE);
    const store = useDashboardStore();
    await store.fetch();
    store.invalidate();
    expect(store.data).toBeNull();
  });
});
