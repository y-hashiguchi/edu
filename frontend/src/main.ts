import { createApp } from 'vue';
import { createPinia } from 'pinia';
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate';
import App from '@/App.vue';
import { router } from '@/router';
import { useAuthStore } from '@/stores/auth';
import { registerTokenGetter, registerUnauthorizedHandler } from '@/lib/api';

const pinia = createPinia();
pinia.use(piniaPluginPersistedstate);

const app = createApp(App);
app.use(pinia);
app.use(router);

const auth = useAuthStore();

// Read auth token from in-memory store (source of truth).
// localStorage is only the persistence layer for cross-reload restore.
registerTokenGetter(() => auth.token);

registerUnauthorizedHandler(() => {
  auth.logout();
  void router.push('/login');
});

// 復帰時に /me を取り直して user state を埋める
if (auth.isAuthenticated) {
  auth.fetchMe().catch(() => {
    auth.logout();
  });
}

app.mount('#app');
