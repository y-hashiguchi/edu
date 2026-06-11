<script setup lang="ts">
/**
 * /admin/users/:id — single-learner drill-down.
 *
 * Shows the four phases with status + latest score, then a list of the
 * learner's submissions. Each submission row links into the submission
 * detail view (where comments and grading history live).
 *
 * Sprint 7: the dashboard section is now per-course. An admin picks
 * which active enrollment to inspect from a selector; the default is
 * the first active enrollment in sort order (which matches the order
 * the backend returns).
 */
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { api } from '@/lib/api';
import ProgressSummaryCard from '@/components/ProgressSummaryCard.vue';
import RecommendationsCard from '@/components/RecommendationsCard.vue';
import WeaknessCard from '@/components/WeaknessCard.vue';
import { useAdminStore } from '@/stores/admin';
import type { AdminDashboardResponse } from '@/types/admin';
import type { CourseCatalogItem } from '@/types/course';

const route = useRoute();
const router = useRouter();
const store = useAdminStore();

const userId = computed(() => String(route.params.id));
const dashboard = ref<AdminDashboardResponse | null>(null);
const selectedCourseSlug = ref<string>('');
const catalog = ref<CourseCatalogItem[]>([]);
const enrollSlug = ref('');
const enrollMessage = ref<string | null>(null);
const enrolling = ref(false);

const activeEnrollments = computed(
  () => store.selectedUser?.enrollments.filter((e) => e.status === 'active') ?? [],
);

const enrollableCourses = computed(() => {
  const enrolled = new Set(
    (store.selectedUser?.enrollments ?? []).map((e) => e.course_slug),
  );
  return catalog.value.filter((c) => !enrolled.has(c.slug));
});

async function reloadDashboard() {
  if (!store.selectedUser || !selectedCourseSlug.value) {
    dashboard.value = null;
    return;
  }
  dashboard.value = await store.fetchUserDashboard(
    store.selectedUser.id,
    selectedCourseSlug.value,
  );
}

async function enrollInCourse() {
  if (!store.selectedUser || !enrollSlug.value) return;
  enrolling.value = true;
  enrollMessage.value = null;
  try {
    await store.enrollUser(store.selectedUser.id, enrollSlug.value);
    enrollMessage.value = 'コースを追加しました';
    enrollSlug.value = '';
    selectedCourseSlug.value =
      activeEnrollments.value[0]?.course_slug ?? '';
    await reloadDashboard();
  } catch (e) {
    enrollMessage.value =
      e instanceof Error ? e.message : 'コース追加に失敗しました';
  } finally {
    enrolling.value = false;
  }
}

async function load() {
  const cat = await api.listCourseCatalog();
  catalog.value = cat.items;
  await store.fetchUserDetail(userId.value);
  await store.fetchSubmissions({ user_id: userId.value });
  // Default the selector to the first active enrollment (the backend
  // returns enrollments sorted by course.sort_order, so this is the
  // primary course). If the learner has no active enrollment we leave
  // the selector empty and the dashboard section unrendered.
  const first = activeEnrollments.value[0];
  selectedCourseSlug.value = first?.course_slug ?? '';
  await reloadDashboard();
}

onMounted(load);
watch(userId, load);

watch(selectedCourseSlug, (slug, prev) => {
  // Skip the initial assignment inside `load()` to avoid a redundant
  // round-trip — `load()` already calls `reloadDashboard()`.
  if (slug === prev) return;
  if (slug) void reloadDashboard();
});

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

      <section
        v-if="enrollableCourses.length > 0"
        class="enroll-box"
      >
        <h2>コース追加</h2>
        <div class="enroll-row">
          <select v-model="enrollSlug" :disabled="enrolling">
            <option value="" disabled>コースを選択…</option>
            <option
              v-for="c in enrollableCourses"
              :key="c.slug"
              :value="c.slug"
            >
              {{ c.title }}
            </option>
          </select>
          <button
            type="button"
            :disabled="enrolling || !enrollSlug"
            @click="enrollInCourse"
          >
            {{ enrolling ? '追加中…' : '追加する' }}
          </button>
        </div>
        <p v-if="enrollMessage" class="enroll-msg">{{ enrollMessage }}</p>
      </section>

      <section
        v-if="activeEnrollments.length > 0"
        class="course-picker"
      >
        <label>
          表示するコース
          <select
            v-model="selectedCourseSlug"
            data-test="course-selector"
          >
            <option
              v-for="e in activeEnrollments"
              :key="e.course_slug"
              :value="e.course_slug"
            >
              {{ e.course_title }}
            </option>
          </select>
        </label>
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
.course-picker {
  margin-top: 1.2rem;
  display: flex;
}
.course-picker label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.82rem;
  color: #6b7280;
}
.course-picker select {
  padding: 0.45rem 0.6rem;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font: inherit;
}
.enroll-box { margin-top: 1.2rem; }
.enroll-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
.enroll-row select {
  flex: 1;
  padding: 0.45rem 0.6rem;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font: inherit;
}
.enroll-row button {
  background: #4f46e5;
  color: #fff;
  border: 0;
  border-radius: 8px;
  padding: 0.45rem 0.9rem;
  font: inherit;
  cursor: pointer;
}
.enroll-row button:disabled { opacity: 0.5; }
.enroll-msg {
  margin: 0.5rem 0 0;
  font-size: 0.85rem;
  color: #047857;
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
