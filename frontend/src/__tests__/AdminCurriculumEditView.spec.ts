import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import type { AdminCurriculumCourseDetail, AdminPhaseEditOut } from '@/types/admin_curriculum';

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { courseSlug: 'ai-driven-dev' } }),
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: {
      ...actual.api,
      adminCurriculumDetail: vi.fn(),
      adminPublishCurriculum: vi.fn(),
      adminDiscardCurriculumDrafts: vi.fn(),
      adminPutCurriculumPhase: vi.fn(),
      adminPutCurriculumTask: vi.fn(),
    },
  };
});

import { api } from '@/lib/api';
import AdminCurriculumEditView from '@/views/admin/AdminCurriculumEditView.vue';

function makePhase(overrides: Partial<AdminPhaseEditOut> = {}): AdminPhaseEditOut {
  return {
    phase_no: 1,
    title: 'Phase 1',
    goal: 'g',
    system_prompt: 's',
    draft_title: null,
    draft_goal: null,
    draft_system_prompt: null,
    updated_at: '2026-06-13T00:00:00Z',
    tasks: [],
    ...overrides,
  };
}

function makeDetail(
  overrides: Partial<AdminCurriculumCourseDetail> = {},
): AdminCurriculumCourseDetail {
  return {
    slug: 'ai-driven-dev',
    title: 'AI駆動開発',
    phases: [makePhase()],
    ...overrides,
  };
}

describe('AdminCurriculumEditView', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('fetches detail on mount and renders phases', async () => {
    (api.adminCurriculumDetail as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue(makeDetail());
    const w = mount(AdminCurriculumEditView);
    await flushPromises();
    expect(api.adminCurriculumDetail).toHaveBeenCalledWith('ai-driven-dev');
    expect(w.html()).toContain('Phase 1');
  });

  it('publish button is disabled when there are no draft fields', async () => {
    (api.adminCurriculumDetail as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue(makeDetail());
    const w = mount(AdminCurriculumEditView);
    await flushPromises();
    const btn = w.find('[data-test="publish-button"]');
    expect((btn.element as HTMLButtonElement).disabled).toBe(true);
    expect(w.find('[data-test="pending-count"]').text()).toContain('0');
  });

  it('confirms publish via modal and shows success message', async () => {
    const detailWithDrafts = makeDetail({
      phases: [
        makePhase({ draft_title: 'new title' }),
        makePhase({ phase_no: 2, draft_goal: 'g2', draft_system_prompt: 'sp2' }),
      ],
    });
    (api.adminCurriculumDetail as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce(detailWithDrafts)
      .mockResolvedValueOnce(makeDetail());
    (api.adminPublishCurriculum as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue({
        slug: 'ai-driven-dev',
        published_phase_count: 2,
        published_task_count: 5,
        published_at: '2026-06-13T00:00:00Z',
      });

    const w = mount(AdminCurriculumEditView);
    await flushPromises();

    const publishBtn = w.find('[data-test="publish-button"]');
    expect((publishBtn.element as HTMLButtonElement).disabled).toBe(false);

    await publishBtn.trigger('click');
    expect(w.find('[data-test="publish-modal"]').exists()).toBe(true);

    await w.find('[data-test="publish-confirm"]').trigger('click');
    await flushPromises();

    expect(api.adminPublishCurriculum).toHaveBeenCalledWith('ai-driven-dev');
    const msg = w.find('[data-test="message"]').text();
    expect(msg).toContain('2 phase');
    expect(msg).toContain('5 task');
  });
});
