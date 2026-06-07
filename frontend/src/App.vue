<script setup lang="ts">
import { computed } from 'vue';
import { RouterView, useRoute, useRouter } from 'vue-router';

import NotificationCenter from '@/components/NotificationCenter.vue';
import { useAuthStore } from '@/stores/auth';

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

const logout = async () => {
  auth.logout();
  await router.push('/login');
};

// Admin routes own their own AdminLayout chrome (header, nav,
// logout). Skipping the global header on /admin/* keeps the visual
// switch into admin mode unambiguous.
const isAdminRoute = computed(() =>
  typeof route.path === 'string' && route.path.startsWith('/admin'),
);
</script>

<template>
  <template v-if="isAdminRoute">
    <RouterView />
  </template>
  <template v-else>
    <header class="app-header">
      <div class="left">
        <h1>AI駆動型開発 補足カリキュラム</h1>
        <p>AIチューター — 学習サポートシステム</p>
      </div>
      <div class="right" v-if="auth.user && route.name !== 'login'">
        <NotificationCenter />
        <span class="who">{{ auth.user.name }} さん</span>
        <button type="button" @click="logout">ログアウト</button>
      </div>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
  </template>
</template>

<style>
:root {
  --color-bg: #f6f7fb;
  --color-surface: #ffffff;
  --color-text: #1b1f24;
  --color-accent: #2f6df6;
  --color-danger: #ef4444;
  --radius: 14px;
}

* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: 'Inter', system-ui, -apple-system, 'Hiragino Kaku Gothic ProN', sans-serif;
  background: var(--color-bg);
  color: var(--color-text);
}

.app-header {
  padding: 1.5rem 2rem;
  background: var(--color-surface);
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}
.app-header h1 { margin: 0; font-size: 1.25rem; }
.app-header p { margin: 0.25rem 0 0; color: #6b7280; font-size: 0.875rem; }
.right { display: flex; align-items: center; gap: 1rem; }
.who { color: #374151; font-size: 0.9rem; }
.right button {
  background: white;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0.4rem 0.8rem;
  cursor: pointer;
  font: inherit;
}
.right button:hover { border-color: var(--color-accent); }

.app-main { padding: 2rem; max-width: 960px; margin: 0 auto; }
</style>
