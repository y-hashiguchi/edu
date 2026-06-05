<script setup lang="ts">
import { ref } from 'vue';
import type { GradingAttempt } from '@/types/curriculum';

defineProps<{
  history: GradingAttempt[];
}>();

const open = ref(false);

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('ja-JP', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}
</script>

<template>
  <div class="history">
    <button
      type="button"
      class="toggle"
      :aria-expanded="open"
      @click="open = !open"
    >
      採点履歴 ({{ history.length }}) {{ open ? '▲' : '▼' }}
    </button>
    <ol v-if="open && history.length" class="entries">
      <li
        v-for="attempt in history"
        :key="attempt.id"
        :class="['entry', attempt.status]"
      >
        <header>
          <span class="time">{{ formatTime(attempt.created_at) }}</span>
          <span class="status">
            {{ attempt.status === 'graded' ? '採点完了' : '採点失敗' }}
          </span>
          <span v-if="attempt.status === 'graded'" class="score">
            {{ attempt.score }} / 100
          </span>
        </header>
        <p v-if="attempt.status === 'graded'" class="feedback">
          {{ attempt.feedback }}
        </p>
        <p v-else class="error">{{ attempt.error_message }}</p>
      </li>
    </ol>
    <p v-if="open && !history.length" class="empty">採点履歴はまだありません。</p>
  </div>
</template>

<style scoped>
.history {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.toggle {
  background: transparent;
  border: 0;
  color: var(--color-accent);
  cursor: pointer;
  font: inherit;
  text-align: left;
  padding: 0.2rem 0;
}
.entries {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.entry {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 0.5rem 0.7rem;
  background: #fff;
}
.entry.failed {
  background: #fef2f2;
  border-color: #fecaca;
}
.entry header {
  display: flex;
  gap: 0.6rem;
  align-items: center;
  font-size: 0.8rem;
  color: #6b7280;
}
.entry .status {
  font-weight: 600;
  color: #111827;
}
.entry .score {
  margin-left: auto;
  font-weight: 700;
}
.feedback,
.error {
  margin: 0.4rem 0 0;
  font-size: 0.9rem;
}
.error {
  color: #b91c1c;
}
.empty {
  font-size: 0.85rem;
  color: #6b7280;
}
</style>
