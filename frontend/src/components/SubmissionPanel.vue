<script setup lang="ts">
import { computed } from 'vue';
import type { PhaseSummary, Submission } from '@/types/curriculum';
import TaskSubmissionCard from '@/components/TaskSubmissionCard.vue';

const props = defineProps<{
  phase: PhaseSummary;
  submissions: Submission[];
  busyTaskNo: number | null;
}>();
const emit = defineEmits<{
  submit: [taskNo: number, content: string];
}>();

const byTaskNo = computed(() => {
  const m: Record<number, Submission> = {};
  for (const s of props.submissions) m[s.task_no] = s;
  return m;
});
</script>

<template>
  <section class="panel">
    <h3>課題提出</h3>
    <TaskSubmissionCard
      v-for="(task, i) in phase.tasks"
      :key="i"
      :task-no="i + 1"
      :task-text="task"
      :submission="byTaskNo[i + 1]"
      :busy="busyTaskNo === i + 1"
      @submit="(no, content) => emit('submit', no, content)"
    />
  </section>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}
.panel h3 {
  margin: 0;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #6b7280;
}
</style>
