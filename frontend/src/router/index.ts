import {
  createRouter,
  createWebHistory,
  type Router,
} from 'vue-router';
import HomeView from '@/views/HomeView.vue';
import PhaseChatView from '@/views/PhaseChatView.vue';
import LoginView from '@/views/LoginView.vue';
import { useAuthStore } from '@/stores/auth';
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
 */
export function attachGuards(router: Router): void {
  router.beforeEach(async (to) => {
    const auth = useAuthStore();
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
    if (to.meta.public !== true && !auth.isAuthenticated) {
      return { name: 'login' };
    }
    if (to.name === 'login' && auth.isAuthenticated) {
      return { name: 'home' };
    }
    if (to.meta.requiresAdmin && !auth.isAdmin) {
      return { name: 'home' };
    }
    return true;
  });
}

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    { path: '/', name: 'home', component: HomeView },
    {
      path: '/phases/:phase',
      name: 'phase',
      component: PhaseChatView,
      props: (route) => ({ phase: Number(route.params.phase) }),
    },
    ...adminRoutes,
  ],
});

attachGuards(router);
