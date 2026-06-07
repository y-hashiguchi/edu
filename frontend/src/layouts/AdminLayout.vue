<script setup lang="ts">
/**
 * AdminLayout — shared chrome for every /admin/* route.
 *
 * The header carries the three admin-side entry points (users, notify,
 * back-to-learner-view) and a logout. The learner-side global header
 * is intentionally NOT reused because the visual switch between admin
 * mode and learner mode is part of the cue that "you're acting on real
 * data now."
 */
import { computed } from 'vue';
import { RouterLink, RouterView, useRouter } from 'vue-router';

import { useAuthStore } from '@/stores/auth';

const auth = useAuthStore();
const router = useRouter();

const adminName = computed(() => auth.user?.name ?? '管理者');

function logout() {
  auth.logout();
  void router.push({ name: 'login' });
}
</script>

<template>
  <div class="admin-shell">
    <header>
      <div class="brand">
        <RouterLink to="/admin/users" class="brand-link">
          AI チューター 管理
        </RouterLink>
        <span class="env-tag">ADMIN</span>
      </div>
      <nav aria-label="Admin navigation">
        <RouterLink to="/admin/users">受講者一覧</RouterLink>
        <RouterLink to="/admin/notify">通知作成</RouterLink>
        <RouterLink to="/">学習者ビュー</RouterLink>
      </nav>
      <div class="who">
        <span class="name">{{ adminName }}</span>
        <button type="button" @click="logout">ログアウト</button>
      </div>
    </header>
    <main>
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.admin-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #0f172a;
  color: #e2e8f0;
}
header {
  display: flex;
  align-items: center;
  gap: 2rem;
  padding: 0.9rem 1.5rem;
  background: #1e293b;
  border-bottom: 1px solid #334155;
}
.brand {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}
.brand-link {
  color: #f8fafc;
  text-decoration: none;
  font-weight: 700;
  font-size: 1.05rem;
}
.env-tag {
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  padding: 2px 8px;
  background: #f59e0b;
  color: #1f2937;
  border-radius: 999px;
}
nav {
  display: flex;
  gap: 1.2rem;
  flex: 1;
}
nav a {
  color: #cbd5e1;
  text-decoration: none;
  font-size: 0.92rem;
  padding: 4px 6px;
  border-radius: 6px;
}
nav a:hover {
  background: #334155;
}
nav a.router-link-active {
  color: #f8fafc;
  background: #334155;
}
.who {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  font-size: 0.85rem;
}
.who button {
  background: transparent;
  color: #cbd5e1;
  border: 1px solid #475569;
  border-radius: 8px;
  padding: 4px 10px;
  font: inherit;
  cursor: pointer;
}
.who button:hover {
  background: #334155;
  color: #f8fafc;
}
main {
  flex: 1;
  padding: 1.5rem;
  background: #f8fafc;
  color: #0f172a;
}
</style>
