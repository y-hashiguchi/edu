import { describe, expect, it, vi, beforeEach } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: {
      ...actual.api,
      submitTask: vi.fn(),
      regradeSubmission: vi.fn(),
      listProgress: vi.fn().mockResolvedValue([]),
      listPhases: vi.fn().mockResolvedValue([]),
    },
  };
});

import { ApiCooldownError, api } from '@/lib/api';
import { useCurriculumStore } from '@/stores/curriculum';
import { useDashboardStore } from '@/stores/dashboard';

describe('curriculum store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('regradeSubmission stores cooldown on success', async () => {
    const store = useCurriculumStore();
    store.submissions[1] = [
      {
        id: 's1',
        phase: 1,
        task_no: 1,
        content: 'x',
        ai_feedback: null,
        score: null,
        submitted_at: '',
        graded_at: null,
        files: [],
        grading_history: [],
      },
    ];
    (api.regradeSubmission as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: 'a1',
      status: 'graded',
      score: 90,
      feedback: 'great',
      error_message: null,
      model_name: 'claude',
      created_at: '2026-06-04T00:00:00Z',
    });

    await store.regradeSubmission(1, 's1');
    expect(store.cooldownSecondsRemaining('s1')).toBeGreaterThan(0);
    const sub = store.submissions[1][0];
    expect(sub.score).toBe(90);
    expect(sub.grading_history).toHaveLength(1);
  });

  it('regradeSubmission stores cooldown on 429 then rethrows', async () => {
    const store = useCurriculumStore();
    (api.regradeSubmission as unknown as ReturnType<typeof vi.fn>).mockRejectedValue(
      new ApiCooldownError(30),
    );
    await expect(store.regradeSubmission(1, 's1')).rejects.toBeInstanceOf(
      ApiCooldownError,
    );
    expect(store.cooldownSecondsRemaining('s1')).toBeGreaterThan(0);
  });

  it('regradeSubmission invalidates the dashboard on a graded result (LOW-2)', async () => {
    // A successful regrade changes the submission's score, which shifts
    // weakness tags, the average, and therefore the nudge signature.
    // submitTask already does the invalidate; regrade must too or the
    // learner sees stale weakness/recommendations until they navigate.
    const store = useCurriculumStore();
    const dashboard = useDashboardStore();
    dashboard.data = { stub: true } as never;  // seed cache

    store.submissions[1] = [
      {
        id: 's1', phase: 1, task_no: 1, content: 'x',
        ai_feedback: null, score: null, submitted_at: '',
        graded_at: null, files: [], grading_history: [],
      },
    ];
    (api.regradeSubmission as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: 'a2', status: 'graded', score: 95, feedback: 'better',
      error_message: null, model_name: 'claude',
      created_at: '2026-06-09T00:00:00Z',
    });

    await store.regradeSubmission(1, 's1');
    expect(dashboard.data).toBeNull();
  });

  it('regradeSubmission does NOT invalidate the dashboard when the attempt failed', async () => {
    // A failed regrade attempt doesn't change the cached graded score,
    // so the dashboard inputs are unchanged. Invalidating here would
    // force a redundant refetch for no UX gain.
    const store = useCurriculumStore();
    const dashboard = useDashboardStore();
    dashboard.data = { stub: true } as never;

    store.submissions[1] = [
      {
        id: 's1', phase: 1, task_no: 1, content: 'x',
        ai_feedback: null, score: null, submitted_at: '',
        graded_at: null, files: [], grading_history: [],
      },
    ];
    (api.regradeSubmission as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: 'a3', status: 'failed', score: null, feedback: null,
      error_message: 'api down', model_name: 'claude',
      created_at: '2026-06-09T00:00:00Z',
    });

    await store.regradeSubmission(1, 's1');
    // invalidate() sets data to null; "did not invalidate" = still truthy.
    expect(dashboard.data).not.toBeNull();
  });
});
