/**
 * Sprint 4 admin routes.
 *
 * Kept in a separate file so adding/removing admin views never
 * touches the learner-side route table — Task 19 fills these in but
 * the route shape is finalised here.
 *
 * Guard wiring lives in router/index.ts (single combined beforeEach).
 * Avoid re-introducing a separate `attachAdminGuard` here: the
 * sprint-4 follow-up MED-5 collapsed the two guards into one so a
 * future refactor cannot reorder them and accidentally allow admin
 * bypass / cause a double-redirect.
 */

import type { RouteRecordRaw } from 'vue-router';

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
