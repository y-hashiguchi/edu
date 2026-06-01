<script setup lang="ts">
import { onMounted } from 'vue';
import { useCurriculumStore } from '@/stores/curriculum';
import PhaseCard from '@/components/PhaseCard.vue';

const store = useCurriculumStore();

onMounted(() => {
  if (store.phases.length === 0) {
    void store.fetchPhases();
  }
});
</script>

<template>
  <section v-if="store.loading">読み込み中…</section>
  <section v-else-if="store.error" class="error">
    エラー: {{ store.error }}
  </section>
  <section v-else class="phase-grid">
    <PhaseCard v-for="p in store.phases" :key="p.phase" :phase="p" />
  </section>
</template>

<style scoped>
.phase-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.25rem;
}
.error {
  background: #fee2e2;
  color: #991b1b;
  padding: 1rem;
  border-radius: 12px;
}
</style>
