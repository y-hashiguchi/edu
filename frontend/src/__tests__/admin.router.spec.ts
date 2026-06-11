import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { createMemoryHistory, createRouter, type Router } from 'vue-router';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: {
      ...actual.api,
      // Sprint 7: the combined guard calls fetchMyCourses for any
      // authenticated route — mock it so the guard doesn't talk to
      // the real backend.
      listMyCourses: vi.fn().mockResolvedValue({ items: [] }),
    },
  };
});

import { useAuthStore } from '@/stores/auth';
import { adminRoutes } from '@/router/admin';
import { attachGuards } from '@/router';

function buildRouter(): Router {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div>home</div>' } },
      // Sprint 7: post-login landing is /courses, so the admin guard
      // bounces non-admins here.
      { path: '/courses', name: 'courses', component: { template: '<div>courses</div>' } },
      { path: '/login', name: 'login', component: { template: '<div>login</div>' } },
      ...adminRoutes,
    ],
  });
  attachGuards(router);
  return router;
}

describe('admin router guard', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('redirects a logged-in non-admin away from /admin/users', async () => {
    const auth = useAuthStore();
    auth.token = 't';
    auth.user = {
      id: 'u1', email: 'a@e.com', name: 'A',
      created_at: '2026-06-06T00:00:00Z', is_admin: false,
    };
    const router = buildRouter();
    await router.push('/admin/users');
    // Non-admins are silently bounced to the courses page — no toast,
    // no 403 page; the admin URL is private, not advertised.
    expect(router.currentRoute.value.name).toBe('courses');
  });

  it('lets an admin through to /admin/users', async () => {
    const auth = useAuthStore();
    auth.token = 't';
    auth.user = {
      id: 'u1', email: 'inst@e.com', name: 'I',
      created_at: '2026-06-06T00:00:00Z', is_admin: true,
    };
    const router = buildRouter();
    await router.push('/admin/users');
    expect(router.currentRoute.value.name).toBe('admin-users');
  });

  it('redirects /admin to /admin/users for an admin', async () => {
    const auth = useAuthStore();
    auth.token = 't';
    auth.user = {
      id: 'u1', email: 'inst@e.com', name: 'I',
      created_at: '2026-06-06T00:00:00Z', is_admin: true,
    };
    const router = buildRouter();
    await router.push('/admin');
    expect(router.currentRoute.value.path).toBe('/admin/users');
  });
});
