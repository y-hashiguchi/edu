<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useCurriculumStore } from '@/stores/curriculum';
import { useDashboardStore } from '@/stores/dashboard';
import PhaseCard from '@/components/PhaseCard.vue';
import NudgeBanner from '@/components/NudgeBanner.vue';
import ProgressSummaryCard from '@/components/ProgressSummaryCard.vue';
import WeaknessCard from '@/components/WeaknessCard.vue';
import RecommendationsCard from '@/components/RecommendationsCard.vue';

const store = useCurriculumStore();
const dashboard = useDashboardStore();
const router = useRouter();
const completed = computed(() => store.completedCount);

onMounted(() => {
  if (store.phases.length === 0) {
    void store.fetchPhasesWithProgress();
  }
  if (dashboard.data === null) {
    void dashboard.fetch();
  }
});

const reload = () => store.fetchPhasesWithProgress();

function onRecommendationClick(coords: { phase: number; task_no: number }) {
  void router.push({ name: 'phase', params: { phase: coords.phase } });
}
</script>

<template>
  <!-- Sprint 5 ダッシュボード -->
  <NudgeBanner v-if="dashboard.data" :nudge="dashboard.data.nudge" />
  <section v-if="dashboard.data" class="dashboard-grid">
    <ProgressSummaryCard :data="dashboard.data.progress_summary" />
    <WeaknessCard :data="dashboard.data.weakness" />
    <RecommendationsCard
      :items="dashboard.data.recommendations.items"
      @select="onRecommendationClick"
    />
  </section>
  <p v-else-if="dashboard.loading" class="dash-loading">ダッシュボード読み込み中…</p>
  <p v-else-if="dashboard.error" class="dash-error">{{ dashboard.error }}</p>

  <!-- 既存フェーズ一覧（下部に保持） -->
  <section v-if="store.loading">読み込み中…</section>
  <section v-else-if="store.error" class="error">
    <p>エラー: {{ store.error }}</p>
    <button type="button" @click="reload">再読み込み</button>
  </section>
  <template v-else>
    <p class="progress-summary">
      あなたの進捗: <strong>{{ completed }} / 4</strong> フェーズ完了
    </p>
    <section class="phase-grid">
      <PhaseCard v-for="p in store.phases" :key="p.phase" :phase="p" />
    </section>
  </template>
</template>

<style scoped>
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 0.9rem;
  margin: 0 0 1.5rem;
}
.dash-loading, .dash-error {
  margin: 0 0 1rem;
  padding: 0.8rem 1rem;
  background: #f9fafb;
  border-radius: 8px;
  color: #6b7280;
  font-size: 0.9rem;
}
.dash-error {
  background: #fef2f2;
  color: #b91c1c;
}
.progress-summary {
  color: #374151;
  font-size: 0.95rem;
  margin: 0 0 1rem;
}
.phase-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1.25rem;
}
.error {
  background: #fee2e2;
  color: #991b1b;
  padding: 1rem;
  border-radius: 12px;
}
.error button {
  margin-top: 0.5rem;
  background: white;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0.4rem 0.8rem;
  cursor: pointer;
}
</style>
