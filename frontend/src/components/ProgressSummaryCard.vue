<script setup lang="ts">
import { computed } from 'vue';
import type { ProgressSummary } from '@/types/dashboard';

const props = defineProps<{ data: ProgressSummary }>();
const COLD_START_THRESHOLD = 3;
// LOW-1 (sprint-5 follow-up): computed so this stays reactive if
// the same component instance is fed a new `data` prop without
// remount (any future surface that mutates dashboard.data in place
// rather than via HomeView's v-if remount).
const belowThreshold = computed(
  () => props.data.submission_count < COLD_START_THRESHOLD,
);
</script>

<template>
  <section
    class="card progress-summary"
    role="region"
    aria-labelledby="progress-heading"
  >
    <h2 id="progress-heading">あなたの進捗</h2>
    <p class="big">
      <span class="num">{{ data.completed_tasks }} / {{ data.total_tasks }}</span>
      <span class="unit">タスク完了</span>
    </p>
    <p class="avg">
      平均スコア:
      <strong v-if="data.average_score !== null">{{ data.average_score }}</strong>
      <strong v-else>—</strong>
    </p>
    <p v-if="belowThreshold" class="hint">
      3 件提出するとあなたの傾向が分析できます（現在 {{ data.submission_count }} 件）。
    </p>
  </section>
</template>

<style scoped>
.card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 1rem 1.2rem;
}
h2 { margin: 0 0 0.6rem; font-size: 0.95rem; color: #374151; }
.big { margin: 0.2rem 0; display: flex; align-items: baseline; gap: 0.4rem; }
.num { font-size: 2rem; font-weight: 700; color: #111827; }
.unit { font-size: 0.85rem; color: #6b7280; }
.avg { margin: 0.4rem 0 0; font-size: 0.9rem; color: #374151; }
.avg strong { color: #111827; font-size: 1.1rem; }
.hint {
  margin: 0.6rem 0 0;
  font-size: 0.8rem;
  color: #6b7280;
  padding: 0.5rem 0.6rem;
  background: #f9fafb;
  border-radius: 6px;
}
</style>
