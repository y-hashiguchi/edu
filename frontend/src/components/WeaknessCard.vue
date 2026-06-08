<script setup lang="ts">
import type { Weakness } from '@/types/dashboard';

defineProps<{ data: Weakness }>();
</script>

<template>
  <section
    class="card weakness"
    role="region"
    aria-labelledby="weakness-heading"
  >
    <h2 id="weakness-heading">もう一押しの分野</h2>
    <p v-if="!data.has_enough_data" class="empty">
      提出 3 件以上で、あなたの傾向を分析して表示します。
    </p>
    <ol v-else-if="data.top_weaknesses.length > 0">
      <li v-for="w in data.top_weaknesses" :key="w.tag">
        <span class="tag">{{ w.tag }}</span>
        <span class="score">平均 {{ w.average_score }}</span>
        <span class="count">（{{ w.submission_count }} 件）</span>
      </li>
    </ol>
    <p v-else class="empty">
      集計に足る提出がまだありません。タグ別に 2 件以上提出すると表示されます。
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
.empty { font-size: 0.85rem; color: #6b7280; margin: 0; }
ol { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.4rem; }
li {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  padding: 0.4rem 0.5rem;
  background: #fef3c7;
  border-radius: 6px;
}
.tag { font-weight: 600; color: #92400e; flex: 0 0 auto; }
.score { font-variant-numeric: tabular-nums; color: #b45309; }
.count { font-size: 0.75rem; color: #9ca3af; }
</style>
