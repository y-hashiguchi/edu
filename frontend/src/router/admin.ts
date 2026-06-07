/**
 * Sprint 4 admin routes.
 *
 * Kept in a separate file so adding/removing admin views never
 * touches the learner-side route table — Task 19 fills these in but
 * the route shape is finalised here.
 *
 * `attachAdminGuard` is registered from router/index.ts alongside the
 * existing auth guard so route matching happens once and both gates
 * apply in declaration order (auth first, then admin).
 */

import type { RouteRecordRaw, Router } from 'vue-router';

import { useAuthStore } from '@/stores/auth';

export const adminRoutes: RouteRecordRaw[] = [
  {
    path: '/admin',
    component: () => import('@/layouts/AdminLayout.vue'),
    meta: { requiresAdmin: true },
    children: [
      { path: '', redirect: '/admin/users' },
      {
        path: 'users',
        name: 'admin-users',
        component: () => import('@/views/admin/AdminUsersView.vue'),
      },
      {
        path: 'users/:id',
        name: 'admin-user-detail',
        component: () => import('@/views/admin/AdminUserDetailView.vue'),
      },
      {
        path: 'submissions/:id',
        name: 'admin-submission-detail',
        component: () => import('@/views/admin/AdminSubmissionDetailView.vue'),
      },
      {
        path: 'notify',
        name: 'admin-notify',
        component: () => import('@/views/admin/AdminNotifyView.vue'),
      },
    ],
  },
];

export function attachAdminGuard(router: Router): void {
  router.beforeEach((to) => {
    if (!to.meta.requiresAdmin) return true;
    const auth = useAuthStore();
    // We rely on the prior auth guard to have already redirected an
    // unauthenticated visitor to /login. Here we only check the admin
    // bit on an already-authenticated user — non-admins land back on
    // the learner home with no error toast (the admin URL is private,
    // not advertised).
    if (!auth.isAdmin) return { name: 'home' };
    return true;
  });
}
