import { beforeEach, describe, expect, it } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { createMemoryHistory, createRouter, type Router } from 'vue-router';

import { useAuthStore } from '@/stores/auth';
import { adminRoutes } from '@/router/admin';
import { attachGuards } from '@/router';

function buildRouter(): Router {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div>home</div>' } },
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
    // Non-admins are silently bounced to the learner home — no toast,
    // no 403 page; the admin URL is private, not advertised.
    expect(router.currentRoute.value.name).toBe('home');
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
