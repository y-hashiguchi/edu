import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: {
      ...actual.api,
      adminCohortSummary: vi.fn(),
    },
  };
});

import { api } from '@/lib/api';
import { useAdminCohortStore } from '@/stores/admin_cohort';

describe('admin_cohort store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('fetchSummary stores response', async () => {
    (api.adminCohortSummary as ReturnType<typeof vi.fn>).mockResolvedValue({
      course_slug: 'ai-driven-dev',
      course_title: 'AI Dev',
      enrolled_count: 3,
      average_score: 72.5,
      completion_rate: 0.25,
      stuck_learners: [],
      tag_heatmap: [],
    });
    const store = useAdminCohortStore();
    await store.fetchSummary('ai-driven-dev');
    expect(store.summary?.enrolled_count).toBe(3);
    expect(store.loading).toBe(false);
    expect(store.error).toBeNull();
  });

  it('fetchSummary records error', async () => {
    (api.adminCohortSummary as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('boom'),
    );
    const store = useAdminCohortStore();
    await store.fetchSummary('ai-driven-dev');
    expect(store.summary).toBeNull();
    expect(store.error).toBe('boom');
  });

  it('fetchSummary updates selectedSlug', async () => {
    (api.adminCohortSummary as ReturnType<typeof vi.fn>).mockResolvedValue({
      course_slug: 'ai-era-se',
      course_title: 'SE',
      enrolled_count: 0,
      average_score: null,
      completion_rate: 0,
      stuck_learners: [],
      tag_heatmap: [],
    });
    const store = useAdminCohortStore();
    await store.fetchSummary('ai-era-se');
    expect(store.selectedSlug).toBe('ai-era-se');
  });
});
