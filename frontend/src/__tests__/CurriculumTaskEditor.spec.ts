import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { mount } from '@vue/test-utils';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: {
      ...actual.api,
      adminPutCurriculumTask: vi.fn(),
      adminCurriculumDetail: vi.fn().mockResolvedValue({
        slug: 'ai-driven-dev', title: 'X', phases: [],
      }),
    },
  };
});

import { api } from '@/lib/api';
import CurriculumTaskEditor from '@/components/admin/CurriculumTaskEditor.vue';
import type { AdminTaskEditOut } from '@/types/admin_curriculum';

function makeTask(overrides: Partial<AdminTaskEditOut> = {}): AdminTaskEditOut {
  return {
    task_no: 1,
    title: 'Original',
    description: 'desc',
    skill_tags: ['Git/GitHub'],
    deliverable: null,
    week_label: null,
    draft_title: null,
    draft_description: null,
    draft_skill_tags: null,
    draft_deliverable: null,
    draft_week_label: null,
    updated_at: '2026-06-13T00:00:00Z',
    ...overrides,
  };
}

describe('CurriculumTaskEditor', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('debounce fires putTask once with the last value', async () => {
    vi.useFakeTimers();
    const w = mount(CurriculumTaskEditor, {
      props: {
        courseSlug: 'ai-driven-dev',
        phaseNo: 1,
        task: makeTask(),
        taskCount: 3,
        canMoveUp: false,
        canMoveDown: true,
      },
    });
    const input = w.find('[data-test="task-title-input"]');
    await input.setValue('A');
    await input.setValue('AB');
    await input.setValue('ABC');
    await vi.advanceTimersByTimeAsync(600);
    expect(api.adminPutCurriculumTask).toHaveBeenCalledTimes(1);
    expect(api.adminPutCurriculumTask).toHaveBeenCalledWith(
      'ai-driven-dev', 1, 1, expect.objectContaining({ title: 'ABC' }),
    );
    vi.useRealTimers();
  });

  it('shows ✏ indicator when draft_title is set', () => {
    const w = mount(CurriculumTaskEditor, {
      props: {
        courseSlug: 'ai-driven-dev',
        phaseNo: 1,
        task: makeTask({ draft_title: 'Draft' }),
        taskCount: 3,
        canMoveUp: false,
        canMoveDown: true,
      },
    });
    expect(w.find('[data-test="title-draft-indicator"]').exists()).toBe(true);
  });
});
