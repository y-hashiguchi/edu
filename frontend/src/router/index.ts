import { createRouter, createWebHistory } from 'vue-router';
import HomeView from '@/views/HomeView.vue';
import PhaseChatView from '@/views/PhaseChatView.vue';
import LoginView from '@/views/LoginView.vue';
import { useAuthStore } from '@/stores/auth';

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
  ],
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (to.meta.public !== true && !auth.isAuthenticated) {
    return { name: 'login' };
  }
  if (to.name === 'login' && auth.isAuthenticated) {
    return { name: 'home' };
  }
  return true;
});
