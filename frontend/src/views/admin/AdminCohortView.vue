<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import { api } from '@/lib/api';
import { useAdminCohortStore } from '@/stores/admin_cohort';

const store = useAdminCohortStore();
const courses = ref<{ slug: string; title: string }[]>([]);

const completionPct = computed(() =>
  store.summary
    ? `${Math.round(store.summary.completion_rate * 100)}%`
    : '—',
);

onMounted(async () => {
  const list = await api.adminCurriculumList();
  courses.value = list.items.map((c) => ({ slug: c.slug, title: c.title }));
  const initial =
    courses.value.find((c) => c.slug === 'ai-driven-dev')?.slug ??
    courses.value[0]?.slug ??
    'ai-driven-dev';
  await store.fetchSummary(initial);
});

async function onCourseChange(event: Event) {
  const slug = (event.target as HTMLSelectElement).value;
  await store.fetchSummary(slug);
}
</script>

<template>
  <section class="cohort-page" data-test="cohort-page">
    <h1>コホート集計</h1>
    <p class="hint">コース単位の受講状況・ stuck 受講者・ skill tag ヒートマップ</p>

    <label class="course-picker">
      コース
      <select
        data-test="course-select"
        :value="store.selectedSlug"
        @change="onCourseChange"
      >
        <option v-for="c in courses" :key="c.slug" :value="c.slug">
          {{ c.title }}
        </option>
      </select>
    </label>

    <p v-if="store.loading" data-test="loading">読み込み中…</p>
    <p v-else-if="store.error" class="error">{{ store.error }}</p>

    <template v-else-if="store.summary">
      <div class="cards">
        <div class="card" data-test="enrolled-count">
          <span class="label">受講者数</span>
          <span class="value">{{ store.summary.enrolled_count }}</span>
        </div>
        <div class="card" data-test="average-score">
          <span class="label">平均スコア</span>
          <span class="value">
            {{
              store.summary.average_score != null
                ? store.summary.average_score
                : '—'
            }}
          </span>
        </div>
        <div class="card" data-test="completion-rate">
          <span class="label">フェーズ完了率</span>
          <span class="value">{{ completionPct }}</span>
        </div>
      </div>

      <h2>stuck 受講者</h2>
      <p v-if="store.summary.stuck_learners.length === 0" data-test="no-stuck">
        stuck 受講者はいません
      </p>
      <table v-else class="table" data-test="stuck-table">
        <thead>
          <tr>
            <th>名前</th>
            <th>メール</th>
            <th>Phase</th>
            <th>提出数</th>
            <th>理由</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="s in store.summary.stuck_learners"
            :key="s.user_id"
          >
            <td>{{ s.display_name }}</td>
            <td>{{ s.email_masked }}</td>
            <td>{{ s.current_phase }}</td>
            <td>{{ s.submission_count }}</td>
            <td>{{ s.reason }}</td>
          </tr>
        </tbody>
      </table>

      <h2>skill tag ヒートマップ</h2>
      <p v-if="store.summary.tag_heatmap.length === 0" data-test="no-tags">
        十分な提出データがありません
      </p>
      <table v-else class="table" data-test="tag-table">
        <thead>
          <tr>
            <th>タグ</th>
            <th>平均スコア</th>
            <th>提出数</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in store.summary.tag_heatmap" :key="t.tag">
            <td>{{ t.tag }}</td>
            <td>{{ t.average_score }}</td>
            <td>{{ t.submission_count }}</td>
          </tr>
        </tbody>
      </table>
    </template>
  </section>
</template>

<style scoped>
.cohort-page {
  max-width: 960px;
  margin: 0 auto;
}
.hint {
  color: #6b7280;
  font-size: 0.9rem;
}
.course-picker {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin: 1rem 0 1.5rem;
  font-size: 0.9rem;
}
.course-picker select {
  max-width: 420px;
  padding: 0.45rem 0.6rem;
  border-radius: 8px;
  border: 1px solid #d1d5db;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}
.card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 1rem;
  background: #fff;
}
.label {
  display: block;
  font-size: 0.8rem;
  color: #6b7280;
}
.value {
  font-size: 1.6rem;
  font-weight: 700;
}
.table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 2rem;
  font-size: 0.9rem;
}
.table th,
.table td {
  border: 1px solid #e5e7eb;
  padding: 0.5rem 0.75rem;
  text-align: left;
}
.error {
  color: #b91c1c;
}
</style>
