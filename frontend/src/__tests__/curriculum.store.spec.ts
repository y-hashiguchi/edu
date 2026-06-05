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
});
