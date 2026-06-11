<script setup lang="ts">
import { computed } from 'vue';
import type { PhaseSummary, Submission } from '@/types/curriculum';
import TaskSubmissionCard from '@/components/TaskSubmissionCard.vue';

const props = defineProps<{
  phase: PhaseSummary;
  submissions: Submission[];
  busyTaskNo: number | null;
  cooldownFor?: (submissionId: string) => number;
  /** Sprint 7: forwarded to TaskSubmissionCard for file downloads. */
  courseSlug: string;
}>();
const emit = defineEmits<{
  submit: [taskNo: number, content: string, files: File[]];
  regrade: [submissionId: string];
}>();

const byTaskNo = computed(() => {
  const m: Record<number, Submission> = {};
  for (const s of props.submissions) m[s.task_no] = s;
  return m;
});

function cooldownSecondsFor(submissionId: string | undefined): number {
  if (!submissionId || !props.cooldownFor) return 0;
  return props.cooldownFor(submissionId);
}
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
      :cooldown-seconds="cooldownSecondsFor(byTaskNo[i + 1]?.id)"
      :course-slug="props.courseSlug"
      @submit="(no, content, files) => emit('submit', no, content, files)"
      @regrade="(id) => emit('regrade', id)"
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
