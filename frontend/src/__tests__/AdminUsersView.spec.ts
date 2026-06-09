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
      adminListUsers: vi.fn().mockResolvedValue({
        items: [
          {
            id: 'u1', email: 'a@e.com', name: 'A',
            created_at: '2026-06-09T00:00:00Z', is_admin: false,
            completed_phases: 1, in_progress_phases: 1,
            top_weakness_tag: 'AI協調',
          },
          {
            id: 'u2', email: 'b@e.com', name: 'B',
            created_at: '2026-06-09T00:00:00Z', is_admin: false,
            completed_phases: 0, in_progress_phases: 0,
            top_weakness_tag: null,
          },
        ],
        total: 2, limit: 50, offset: 0,
      }),
    },
  };
});

import AdminUsersView from '@/views/admin/AdminUsersView.vue';

function buildRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/admin/users', name: 'admin-users', component: AdminUsersView },
      {
        path: '/admin/users/:id',
        name: 'admin-user-detail',
        component: { template: '<div>detail</div>' },
      },
    ],
  });
}

describe('AdminUsersView (Sprint 6)', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('shows top_weakness_tag for each user', async () => {
    const router = buildRouter();
    await router.push('/admin/users');
    const w = mount(AdminUsersView, { global: { plugins: [router] } });
    await flushPromises();
    expect(w.text()).toContain('AI協調');
  });

  it('shows em dash when top_weakness_tag is null', async () => {
    const router = buildRouter();
    await router.push('/admin/users');
    const w = mount(AdminUsersView, { global: { plugins: [router] } });
    await flushPromises();
    expect(w.text()).toContain('—');
  });

  it('renders header "もう一押し"', async () => {
    const router = buildRouter();
    await router.push('/admin/users');
    const w = mount(AdminUsersView, { global: { plugins: [router] } });
    await flushPromises();
    expect(w.text()).toContain('もう一押し');
  });
});
