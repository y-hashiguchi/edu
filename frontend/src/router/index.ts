import {
  createRouter,
  createWebHistory,
  type Router,
} from 'vue-router';
import HomeView from '@/views/HomeView.vue';
import PhaseChatView from '@/views/PhaseChatView.vue';
import LoginView from '@/views/LoginView.vue';
import CourseListView from '@/views/CourseListView.vue';
import { useAuthStore } from '@/stores/auth';
import { useCourseStore } from '@/stores/course';
import { adminRoutes } from '@/router/admin';

/**
 * MED-5 (sprint-4 security follow-up): a single combined beforeEach
 * hydrates auth, gates non-public routes, redirects authenticated
 * users away from /login, and enforces `requiresAdmin`. The previous
 * design layered two separate guards and worked only because Vue
 * Router happens to call them in registration order — a future
 * refactor could reorder them and accidentally evaluate `isAdmin`
 * before the hydrate step ran, briefly admitting non-admins to
 * /admin/*. One guard makes the dependency explicit.
 *
 * Sprint 7: the same guard also hydrates the course store. Without
 * this, a hard reload of /courses/:slug/* would land on a route
 * whose components read `useCourseStore().activeSlug` before any
 * fetch has run.
 */
export function attachGuards(router: Router): void {
  router.beforeEach(async (to) => {
    const auth = useAuthStore();
    const course = useCourseStore();
    // Only the JWT token survives a hard reload (persist paths=['token']).
    // Hydrate `user` before reading `auth.isAdmin` or `auth.user.name` —
    // otherwise admins would silently bounce off /admin/* after a refresh.
    if (auth.token && !auth.user) {
      try {
        await auth.fetchMe();
      } catch {
        auth.logout();
      }
    }
    if (auth.isAuthenticated) {
      // Sprint 7: pull the active slug out of localStorage so deep
      // links into /courses/:slug/* feel instant, then make sure
      // myCourses is populated for guard decisions further down (and
      // for the LoginView post-login routing fallback).
      course.hydrateActiveFromStorage();
      if (!course.loaded) {
        try {
          await course.fetchMyCourses();
        } catch {
          // Non-fatal: views will show their own load errors.
        }
      }
    }
    if (to.meta.public !== true && !auth.isAuthenticated) {
      return { name: 'login' };
    }
    if (to.name === 'login' && auth.isAuthenticated) {
      return { name: 'courses' };
    }
    if (to.meta.requiresAdmin && !auth.isAdmin) {
      return { name: 'courses' };
    }
    return true;
  });
}

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    // Sprint 7: root now funnels everyone through the course list.
    { path: '/', redirect: { name: 'courses' } },
    { path: '/courses', name: 'courses', component: CourseListView },
    {
      path: '/courses/:courseSlug',
      name: 'course-home',
      component: HomeView,
      props: (route) => ({ courseSlug: String(route.params.courseSlug) }),
    },
    {
      path: '/courses/:courseSlug/phases/:phase',
      name: 'course-phase',
      component: PhaseChatView,
      props: (route) => ({
        courseSlug: String(route.params.courseSlug),
        phase: Number(route.params.phase),
      }),
    },
    // Sprint 7 back-compat: redirect bare /phases/:phase to the
    // default course (matches the backend's DEFAULT_COURSE_SLUG).
    {
      path: '/phases/:phase',
      redirect: (to) => ({
        name: 'course-phase',
        params: {
          courseSlug: 'ai-driven-dev',
          phase: to.params.phase,
        },
      }),
    },
    ...adminRoutes,
  ],
});

attachGuards(router);
