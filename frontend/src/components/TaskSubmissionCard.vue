<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { Submission } from '@/types/curriculum';

const props = defineProps<{
  taskNo: number;
  taskText: string;
  submission?: Submission;
  busy: boolean;
}>();
const emit = defineEmits<{
  submit: [taskNo: number, content: string];
}>();

const draft = ref(props.submission?.content ?? '');
watch(
  () => props.submission?.content,
  (v) => {
    if (v !== undefined) draft.value = v;
  },
);

const isGraded = computed(() => props.submission?.score != null);
const scoreLabel = computed(() =>
  isGraded.value ? `${props.submission!.score} / 100` : '採点中…',
);

const send = () => {
  if (!draft.value.trim()) return;
  emit('submit', props.taskNo, draft.value.trim());
};
</script>

<template>
  <article class="task-card">
    <header>
      <span class="num">Task {{ taskNo }}</span>
      <span v-if="submission" class="badge" :class="{ graded: isGraded }">
        {{ scoreLabel }}
      </span>
    </header>
    <p class="desc">{{ taskText }}</p>

    <textarea
      v-model="draft"
      rows="4"
      placeholder="提出内容を記入してください..."
      :disabled="busy"
    />

    <div v-if="submission?.ai_feedback" class="feedback">
      <strong>AI フィードバック:</strong>
      <p>{{ submission.ai_feedback }}</p>
    </div>

    <button type="button" :disabled="busy || !draft.trim()" @click="send">
      {{ submission ? '再提出する' : '提出する' }}
    </button>
  </article>
</template>

<style scoped>
.task-card {
  background: var(--color-surface);
  border-radius: var(--radius);
  padding: 1rem 1.25rem;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.04);
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}
.task-card header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.num { font-size: 0.8rem; font-weight: 600; color: var(--color-accent); }
.badge {
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 999px;
  background: #fef3c7;
  color: #92400e;
}
.badge.graded { background: #dcfce7; color: #166534; }
.desc { margin: 0; font-size: 0.92rem; }
textarea {
  resize: vertical;
  min-height: 88px;
  font: inherit;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0.6rem;
}
.feedback {
  background: #f9fafb;
  padding: 0.6rem 0.9rem;
  border-radius: 10px;
}
.feedback p { margin: 0.3rem 0 0; color: #374151; font-size: 0.9rem; }
button {
  align-self: flex-start;
  background: var(--color-accent);
  color: white;
  border: 0;
  border-radius: 10px;
  padding: 0.5rem 1rem;
  cursor: pointer;
  font: inherit;
}
button:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
