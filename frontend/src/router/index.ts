import { createRouter, createWebHistory } from 'vue-router';
import HomeView from '@/views/HomeView.vue';
import PhaseChatView from '@/views/PhaseChatView.vue';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    {
      path: '/phases/:phase',
      name: 'phase',
      component: PhaseChatView,
      props: (route) => ({ phase: Number(route.params.phase) }),
    },
  ],
});
