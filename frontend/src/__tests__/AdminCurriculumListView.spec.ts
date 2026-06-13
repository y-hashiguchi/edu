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
    },
  };
});

vi.mock('vue-router', () => ({
  RouterLink: { template: '<a><slot /></a>' },
}));

import { api } from '@/lib/api';
import AdminCurriculumListView from '@/views/admin/AdminCurriculumListView.vue';

describe('AdminCurriculumListView', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('renders course summary cards', async () => {
    (api.adminCurriculumList as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue({
        items: [
          { slug: 'ai-driven-dev', title: 'AI Dev', pending_draft_count: 0 },
          { slug: 'ai-era-se', title: 'SE', pending_draft_count: 3 },
        ],
      });
    const w = mount(AdminCurriculumListView);
    await flushPromises();
    expect(w.text()).toContain('AI Dev');
    expect(w.text()).toContain('SE');
  });

  it('shows draft badge only when pending_draft_count > 0', async () => {
    (api.adminCurriculumList as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue({
        items: [
          { slug: 'a', title: 'A', pending_draft_count: 0 },
          { slug: 'b', title: 'B', pending_draft_count: 5 },
        ],
      });
    const w = mount(AdminCurriculumListView);
    await flushPromises();
    const badges = w.findAll('[data-test="draft-badge"]');
    expect(badges).toHaveLength(1);
    expect(badges[0].text()).toContain('5');
  });
});
