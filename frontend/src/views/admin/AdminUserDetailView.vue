<script setup lang="ts">
/**
 * /admin/users/:id — single-learner drill-down.
 *
 * Shows the four phases with status + latest score, then a list of the
 * learner's submissions. Each submission row links into the submission
 * detail view (where comments and grading history live).
 */
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import ProgressSummaryCard from '@/components/ProgressSummaryCard.vue';
import RecommendationsCard from '@/components/RecommendationsCard.vue';
import WeaknessCard from '@/components/WeaknessCard.vue';
import { useAdminStore } from '@/stores/admin';
import type { AdminDashboardResponse } from '@/types/admin';

const route = useRoute();
const router = useRouter();
const store = useAdminStore();

const userId = computed(() => String(route.params.id));
const dashboard = ref<AdminDashboardResponse | null>(null);

async function load() {
  await store.fetchUserDetail(userId.value);
  await store.fetchSubmissions({ user_id: userId.value });
  // Sprint 6: 受講者ダッシュボード (nudge なし)
  dashboard.value = await store.fetchUserDashboard(userId.value);
}

onMounted(load);
watch(userId, load);

function gotoSubmission(submissionId: string) {
  void router.push({ name: 'admin-submission-detail', params: { id: submissionId } });
}

function phaseStatusLabel(status: string): string {
  switch (status) {
    case 'completed': return '完了';
    case 'in_progress': return '進行中';
    case 'submitted': return '提出済み';
    case 'locked':
    default: return 'ロック中';
  }
}
</script>

<template>
  <section class="panel">
    <RouterLink to="/admin/users" class="back">← 一覧に戻る</RouterLink>

    <p v-if="store.error" class="error">{{ store.error }}</p>

    <template v-if="store.selectedUser">
      <header class="head">
        <div>
          <h1>{{ store.selectedUser.name }}</h1>
          <p class="email">{{ store.selectedUser.email }}</p>
        </div>
        <span v-if="store.selectedUser.is_admin" class="badge admin">admin</span>
      </header>

      <section class="phases">
        <h2>フェーズ進捗</h2>
        <div class="grid">
          <article
            v-for="p in store.selectedUser.progress"
            :key="p.phase"
            class="phase-card"
            :class="`status-${p.status}`"
          >
            <header>
              <span class="phase-no">Phase {{ p.phase }}</span>
              <span class="status">{{ phaseStatusLabel(p.status) }}</span>
            </header>
            <p class="score">
              最新スコア:
              <strong>
                {{
                  store.selectedUser.latest_scores[String(p.phase)] ?? '—'
                }}
              </strong>
            </p>
          </article>
        </div>
      </section>

      <section v-if="dashboard" class="user-dashboard-section">
        <h2>受講者のダッシュボード</h2>
        <div class="dash-grid">
          <ProgressSummaryCard :data="dashboard.progress_summary" />
          <WeaknessCard :data="dashboard.weakness" />
          <RecommendationsCard
            :items="dashboard.recommendations.items"
            @select="() => {}"
          />
        </div>
      </section>
      <p v-else-if="store.dashboardError" class="dash-error">
        {{ store.dashboardError }}
      </p>

      <section class="submissions">
        <h2>提出物</h2>
        <p v-if="store.submissions.length === 0" class="loading">
          このユーザーの提出はまだありません。
        </p>
        <ul v-else>
          <li v-for="s in store.submissions" :key="s.id" @click="gotoSubmission(s.id)">
            <div class="sub-head">
              <span class="phase-no">Phase {{ s.phase }} / Task {{ s.task_no }}</span>
              <span class="score">
                {{ s.score != null ? `${s.score} 点` : '採点待ち' }}
              </span>
            </div>
            <time>{{ new Date(s.submitted_at).toLocaleString('ja-JP') }}</time>
          </li>
        </ul>
      </section>
    </template>

    <p v-else-if="store.loading" class="loading">読み込み中…</p>
  </section>
</template>

<style scoped>
.panel {
  background: #fff;
  border-radius: 12px;
  padding: 1.4rem;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.06);
}
.back {
  display: inline-block;
  margin-bottom: 1rem;
  color: #4f46e5;
  text-decoration: none;
  font-size: 0.88rem;
}
.back:hover { text-decoration: underline; }
.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.7rem;
  border-bottom: 1px solid #e5e7eb;
  padding-bottom: 1rem;
}
h1 { margin: 0; font-size: 1.2rem; }
.email { margin: 0.2rem 0 0; color: #6b7280; font-size: 0.9rem; }
.error { color: #b91c1c; font-size: 0.9rem; }
.loading { color: #6b7280; font-size: 0.9rem; }
.badge.admin {
  background: #fef3c7;
  color: #92400e;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
}
h2 {
  margin: 1.4rem 0 0.7rem;
  font-size: 0.95rem;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 0.8rem;
}
.phase-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 0.8rem;
}
.phase-card header {
  display: flex;
  justify-content: space-between;
  font-size: 0.78rem;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.phase-card .phase-no { font-weight: 700; color: #4f46e5; }
.phase-card.status-completed { background: #ecfdf5; border-color: #a7f3d0; }
.phase-card.status-in_progress { background: #fefce8; border-color: #fde68a; }
.phase-card.status-submitted { background: #eff6ff; border-color: #bfdbfe; }
.phase-card.status-locked { background: #f9fafb; color: #9ca3af; }
.phase-card .score {
  margin: 0.5rem 0 0;
  font-size: 0.95rem;
}
.submissions ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.submissions li {
  background: #f9fafb;
  border-radius: 10px;
  padding: 0.7rem 0.9rem;
  cursor: pointer;
}
.submissions li:hover { background: #f1f5f9; }
.sub-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  font-size: 0.92rem;
}
.sub-head .phase-no { font-weight: 600; color: #4f46e5; }
.sub-head .score { color: #1f2937; font-variant-numeric: tabular-nums; }
.submissions time { font-size: 0.78rem; color: #6b7280; }
.user-dashboard-section .dash-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 0.9rem;
}
.dash-error {
  margin: 1.4rem 0 0;
  padding: 0.8rem 1rem;
  background: #fef2f2;
  color: #b91c1c;
  border: 1px solid #fecaca;
  border-radius: 8px;
  font-size: 0.9rem;
}
</style>
