<script setup lang="ts">
/**
 * /admin/users — paginated learner list.
 *
 * Row click navigates to the per-user drill-down. Pagination is offset
 * based (matches the backend) and uses URL-less local state for now —
 * URL-as-state for filters lands in a later sprint.
 */
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { useAdminStore } from '@/stores/admin';

const PAGE_SIZE = 50;

const store = useAdminStore();
const router = useRouter();

const offset = ref(0);

onMounted(() => {
  void store.fetchUsers(PAGE_SIZE, offset.value);
});

const totalPages = computed(() =>
  Math.max(1, Math.ceil(store.usersTotal / PAGE_SIZE)),
);
const currentPage = computed(() => Math.floor(offset.value / PAGE_SIZE) + 1);

async function setPage(p: number) {
  const clamped = Math.max(1, Math.min(totalPages.value, p));
  offset.value = (clamped - 1) * PAGE_SIZE;
  await store.fetchUsers(PAGE_SIZE, offset.value);
}

function gotoUser(userId: string) {
  void router.push({ name: 'admin-user-detail', params: { id: userId } });
}
</script>

<template>
  <section class="panel">
    <header class="head">
      <h1>受講者一覧</h1>
      <p class="meta">{{ store.usersTotal }} 名</p>
    </header>

    <p v-if="store.error" class="error">{{ store.error }}</p>

    <table v-if="!store.loading && store.users.length > 0" class="users">
      <thead>
        <tr>
          <th>名前</th>
          <th>メール</th>
          <th class="num">完了</th>
          <th class="num">進行中</th>
          <th>もう一押し</th>
          <th>登録日</th>
          <th>権限</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in store.users" :key="u.id" @click="gotoUser(u.id)">
          <td class="name">{{ u.name }}</td>
          <td>{{ u.email }}</td>
          <td class="num">{{ u.completed_phases }} / 4</td>
          <td class="num">{{ u.in_progress_phases }}</td>
          <td>
            <span v-if="u.top_weakness_tag" class="tag">{{ u.top_weakness_tag }}</span>
            <span v-else class="muted">—</span>
          </td>
          <td>{{ new Date(u.created_at).toLocaleDateString('ja-JP') }}</td>
          <td>
            <span v-if="u.is_admin" class="badge admin">admin</span>
            <span v-else class="badge learner">受講者</span>
          </td>
        </tr>
      </tbody>
    </table>

    <p v-else-if="store.loading" class="loading">読み込み中…</p>
    <p v-else class="loading">受講者がいません。</p>

    <footer v-if="totalPages > 1" class="pager">
      <button type="button" :disabled="currentPage <= 1" @click="setPage(currentPage - 1)">
        前へ
      </button>
      <span>{{ currentPage }} / {{ totalPages }}</span>
      <button
        type="button"
        :disabled="currentPage >= totalPages"
        @click="setPage(currentPage + 1)"
      >
        次へ
      </button>
    </footer>
  </section>
</template>

<style scoped>
.panel {
  background: #fff;
  border-radius: 12px;
  padding: 1.4rem;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.06);
}
.head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 1rem;
}
h1 {
  margin: 0;
  font-size: 1.15rem;
}
.meta {
  margin: 0;
  font-size: 0.8rem;
  color: #6b7280;
}
.error {
  color: #b91c1c;
  font-size: 0.9rem;
}
.loading {
  color: #6b7280;
  font-size: 0.9rem;
}
table.users {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.92rem;
}
th, td {
  padding: 0.55rem 0.7rem;
  text-align: left;
  border-bottom: 1px solid #e5e7eb;
}
th {
  background: #f9fafb;
  font-size: 0.78rem;
  font-weight: 600;
  color: #4b5563;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
td.num, th.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
tbody tr {
  cursor: pointer;
}
tbody tr:hover {
  background: #f1f5f9;
}
.name {
  font-weight: 600;
}
.badge {
  font-size: 0.72rem;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
}
.badge.admin {
  background: #fef3c7;
  color: #92400e;
}
.badge.learner {
  background: #e0e7ff;
  color: #3730a3;
}
.tag {
  background: #fef3c7;
  color: #92400e;
  font-size: 0.78rem;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 6px;
}
.muted {
  color: #9ca3af;
}
.pager {
  margin-top: 1.2rem;
  display: flex;
  align-items: center;
  gap: 0.8rem;
  justify-content: flex-end;
  font-size: 0.9rem;
}
.pager button {
  background: #fff;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 0.35rem 0.75rem;
  font: inherit;
  cursor: pointer;
}
.pager button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
