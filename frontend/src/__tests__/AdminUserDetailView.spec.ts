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
      adminGetUser: vi.fn().mockResolvedValue({
        id: 'u1', email: 'a@e.com', name: 'A',
        created_at: '2026-06-09T00:00:00Z', is_admin: false,
        progress: [
          { phase: 1, status: 'completed' },
          { phase: 2, status: 'in_progress' },
          { phase: 3, status: 'locked' },
          { phase: 4, status: 'locked' },
        ],
        latest_scores: { '1': 80, '2': null, '3': null, '4': null },
      }),
      adminListSubmissions: vi.fn().mockResolvedValue({
        items: [], total: 0, limit: 50, offset: 0,
      }),
      getAdminUserDashboard: vi.fn().mockResolvedValue({
        progress_summary: {
          completed_tasks: 5, total_tasks: 12,
          submission_count: 5, average_score: 72,
        },
        weakness: {
          has_enough_data: true,
          top_weaknesses: [
            { tag: 'AI協調', average_score: 60, submission_count: 3 },
          ],
        },
        recommendations: { items: [] },
      }),
    },
  };
});

import AdminUserDetailView from '@/views/admin/AdminUserDetailView.vue';

function buildRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/admin/users/:id',
        name: 'admin-user-detail',
        component: AdminUserDetailView,
      },
      {
        path: '/admin/users',
        name: 'admin-users',
        component: { template: '<div>list</div>' },
      },
      {
        path: '/admin/submissions/:id',
        name: 'admin-submission-detail',
        component: { template: '<div>sub</div>' },
      },
    ],
  });
}

describe('AdminUserDetailView (Sprint 6)', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('renders the dashboard section without a nudge banner', async () => {
    const router = buildRouter();
    await router.push('/admin/users/u1');
    const w = mount(AdminUserDetailView, { global: { plugins: [router] } });
    await flushPromises();
    expect(w.text()).toContain('受講者のダッシュボード');
    expect(w.text()).toContain('もう一押しの分野');
    expect(w.text()).toContain('あなたの進捗');
    // nudge セクションは admin 経路にはない
    expect(w.text()).not.toContain('今日のアドバイス');
  });

  it('shows the top_weakness_tag from the dashboard response', async () => {
    const router = buildRouter();
    await router.push('/admin/users/u1');
    const w = mount(AdminUserDetailView, { global: { plugins: [router] } });
    await flushPromises();
    expect(w.text()).toContain('AI協調');
  });
});
