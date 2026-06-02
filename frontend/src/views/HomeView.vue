<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useCurriculumStore } from '@/stores/curriculum';
import PhaseCard from '@/components/PhaseCard.vue';

const store = useCurriculumStore();
const completed = computed(() => store.completedCount);

onMounted(() => {
  if (store.phases.length === 0) {
    void store.fetchPhasesWithProgress();
  }
});

const reload = () => store.fetchPhasesWithProgress();
</script>

<template>
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
