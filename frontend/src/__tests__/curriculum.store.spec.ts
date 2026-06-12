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
      getMySubmission: vi.fn(),
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

    await store.regradeSubmission(1, 's1', 'ai-driven-dev');
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
    await expect(store.regradeSubmission(1, 's1', 'ai-driven-dev')).rejects.toBeInstanceOf(
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

    await store.regradeSubmission(1, 's1', 'ai-driven-dev');
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

    await store.regradeSubmission(1, 's1', 'ai-driven-dev');
    // invalidate() sets data to null; "did not invalidate" = still truthy.
    expect(dashboard.data).not.toBeNull();
  });

  it('submitTask starts pollSubmissionById when grading is async (graded_at null)', async () => {
    // Sprint 8 + follow-up: the async grading path returns a row with
    // graded_at=null. submitTask must trigger the single-submission
    // poller (not the legacy phase-list poller) so the worker's later
    // write lands in the store without an extra full-list fetch.
    const store = useCurriculumStore();
    (api.submitTask as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: 's-new', phase: 1, task_no: 1, content: 'x',
      ai_feedback: null, score: null, submitted_at: '',
      graded_at: null, files: [], grading_history: [],
    });
    // pollSubmissionById awaits 2s before its first call — return a
    // pending row so the poll loop continues and we can assert the
    // single API was invoked exactly once before the test ends.
    (api.getMySubmission as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: 's-new', phase: 1, task_no: 1, content: 'x',
      ai_feedback: null, score: null, submitted_at: '',
      graded_at: null, files: [], grading_history: [],
    });

    vi.useFakeTimers();
    try {
      const promise = store.submitTask(1, 1, 'x', [], 'ai-driven-dev');
      // submitTask is awaited (it returns the initial submission); the
      // pollSubmissionById call is fire-and-forget.
      const submission = await promise;
      expect(submission.id).toBe('s-new');

      // Advance just past the first poll tick to confirm the new
      // GET endpoint is used.
      await vi.advanceTimersByTimeAsync(2100);
      expect(api.getMySubmission).toHaveBeenCalledWith('s-new');
    } finally {
      vi.useRealTimers();
    }
  });

  it('regradeSubmission marks the row pending and does not merge on async path', async () => {
    // Sprint 8 follow-up: async regrade returns a synthetic PENDING
    // attempt. The store should NOT call _mergeAttempt (which would
    // overwrite ai_feedback with "採点エラー: undefined") and should
    // clear graded_at so the UI shows "採点中".
    const store = useCurriculumStore();
    const previousFeedback = 'previous: 80 nice';
    store.submissions[1] = [
      {
        id: 's1', phase: 1, task_no: 1, content: 'x',
        ai_feedback: previousFeedback, score: 80,
        submitted_at: '', graded_at: '2026-06-11T00:00:00Z',
        files: [], grading_history: [],
      },
    ];
    (api.regradeSubmission as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: 'pending-1', status: 'pending', score: null, feedback: null,
      error_message: null, model_name: '(pending)',
      created_at: '2026-06-11T01:00:00Z',
    });
    // Block the poll loop from racing the assertion: have getMySubmission
    // return a still-pending row so pollSubmissionById doesn't terminate.
    (api.getMySubmission as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: 's1', phase: 1, task_no: 1, content: 'x',
      ai_feedback: previousFeedback, score: 80,
      submitted_at: '', graded_at: null,
      files: [], grading_history: [],
    });

    const attempt = await store.regradeSubmission(1, 's1', 'ai-driven-dev');
    expect(attempt.status).toBe('pending');
    const sub = store.submissions[1][0];
    // graded_at cleared → UI surfaces the "採点中" state.
    expect(sub.graded_at).toBeNull();
    // Previous feedback / score / history must NOT be overwritten by the
    // synthetic pending attempt.
    expect(sub.ai_feedback).toBe(previousFeedback);
    expect(sub.score).toBe(80);
    expect(sub.grading_history).toHaveLength(0);
    // No cooldown stored for a pending attempt (we don't know yet if it
    // will succeed; the cooldown is server-side anyway).
    expect(store.cooldownSecondsRemaining('s1')).toBe(0);
  });
});
