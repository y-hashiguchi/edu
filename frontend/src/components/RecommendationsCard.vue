<script setup lang="ts">
import type { RecommendationItem } from '@/types/dashboard';

defineProps<{ items: RecommendationItem[] }>();
const emit = defineEmits<{ select: [{ phase: number; task_no: number }] }>();

function onClick(item: RecommendationItem) {
  emit('select', { phase: item.phase, task_no: item.task_no });
}
</script>

<template>
  <section
    class="card recs"
    role="region"
    aria-labelledby="recs-heading"
  >
    <h2 id="recs-heading">次のおすすめ</h2>
    <ol v-if="items.length > 0">
      <li v-for="item in items" :key="`${item.phase}-${item.task_no}`">
        <button type="button" class="rec" @click="onClick(item)">
          <div class="meta">
            <span class="ph">Phase {{ item.phase }} / Task {{ item.task_no }}</span>
            <span v-if="item.match_tag" class="match">#{{ item.match_tag }}</span>
          </div>
          <p class="title">{{ item.title }}</p>
        </button>
      </li>
    </ol>
    <p v-else class="empty">
      まだおすすめできるデータが揃っていません。Phase 1 のタスクから始めてみましょう。
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
ol { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.5rem; }
.rec {
  width: 100%;
  text-align: left;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 0.6rem 0.7rem;
  cursor: pointer;
  font: inherit;
  color: inherit;
}
.rec:hover { background: #f3f4f6; }
.meta {
  display: flex; gap: 0.5rem; align-items: baseline;
  font-size: 0.72rem; color: #6b7280;
}
.match { color: #b45309; font-weight: 600; }
.title { margin: 0.3rem 0 0; font-size: 0.9rem; font-weight: 500; color: #111827; }
.empty { margin: 0; font-size: 0.85rem; color: #6b7280; }
</style>
