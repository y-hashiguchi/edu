import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { mount, flushPromises } from '@vue/test-utils';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: {
      ...actual.api,
      adminCurriculumList: vi.fn(),
      adminCohortSummary: vi.fn(),
      downloadCohortCsv: vi.fn(),
    },
  };
});

import { api } from '@/lib/api';
import AdminCohortView from '@/views/admin/AdminCohortView.vue';

describe('AdminCohortView', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('renders cohort summary cards', async () => {
    (api.adminCurriculumList as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [{ slug: 'ai-driven-dev', title: 'AI Dev', pending_draft_count: 0 }],
    });
    (api.adminCohortSummary as ReturnType<typeof vi.fn>).mockResolvedValue({
      course_slug: 'ai-driven-dev',
      course_title: 'AI Dev',
      enrolled_count: 5,
      average_score: 68,
      completion_rate: 0.4,
      stuck_learners: [],
      tag_heatmap: [],
    });
    const w = mount(AdminCohortView);
    await flushPromises();
    expect(w.get('[data-test="enrolled-count"]').text()).toContain('5');
    expect(w.get('[data-test="average-score"]').text()).toContain('68');
    expect(w.get('[data-test="completion-rate"]').text()).toContain('40%');
  });

  it('shows stuck table when learners exist', async () => {
    (api.adminCurriculumList as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [{ slug: 'ai-driven-dev', title: 'AI Dev', pending_draft_count: 0 }],
    });
    (api.adminCohortSummary as ReturnType<typeof vi.fn>).mockResolvedValue({
      course_slug: 'ai-driven-dev',
      course_title: 'AI Dev',
      enrolled_count: 1,
      average_score: null,
      completion_rate: 0,
      stuck_learners: [
        {
          user_id: 'u1',
          display_name: '山田',
          email_masked: 'ya***@example.com',
          last_activity_at: null,
          current_phase: 1,
          submission_count: 0,
          reason: 'no_submissions',
        },
      ],
      tag_heatmap: [],
    });
    const w = mount(AdminCohortView);
    await flushPromises();
    expect(w.get('[data-test="stuck-table"]').text()).toContain('山田');
  });

  it('shows tag heatmap table', async () => {
    (api.adminCurriculumList as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [{ slug: 'ai-driven-dev', title: 'AI Dev', pending_draft_count: 0 }],
    });
    (api.adminCohortSummary as ReturnType<typeof vi.fn>).mockResolvedValue({
      course_slug: 'ai-driven-dev',
      course_title: 'AI Dev',
      enrolled_count: 2,
      average_score: 80,
      completion_rate: 0.5,
      stuck_learners: [],
      tag_heatmap: [
        { tag: 'Git/GitHub', average_score: 70, submission_count: 3 },
      ],
    });
    const w = mount(AdminCohortView);
    await flushPromises();
    expect(w.get('[data-test="tag-table"]').text()).toContain('Git/GitHub');
  });

  it('triggers CSV download when export is clicked', async () => {
    (api.adminCurriculumList as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [{ slug: 'ai-driven-dev', title: 'AI Dev', pending_draft_count: 0 }],
    });
    (api.adminCohortSummary as ReturnType<typeof vi.fn>).mockResolvedValue({
      course_slug: 'ai-driven-dev',
      course_title: 'AI Dev',
      enrolled_count: 2,
      average_score: 80,
      completion_rate: 0.5,
      stuck_learners: [],
      tag_heatmap: [],
    });
    (api.downloadCohortCsv as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Blob(['course_slug,course_title'], { type: 'text/csv' }),
    );

    const w = mount(AdminCohortView);
    await flushPromises();
    await w.get('[data-test="export-csv"]').trigger('click');
    await flushPromises();

    expect(api.downloadCohortCsv).toHaveBeenCalledWith('ai-driven-dev');
  });
});
