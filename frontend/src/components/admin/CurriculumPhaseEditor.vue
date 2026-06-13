<script setup lang="ts">
import { computed, ref } from 'vue';
import { useAdminCurriculumStore } from '@/stores/admin_curriculum';
import CurriculumTaskEditor from './CurriculumTaskEditor.vue';
import type { AdminPhaseEditOut } from '@/types/admin_curriculum';

const props = defineProps<{
  courseSlug: string;
  phase: AdminPhaseEditOut;
}>();

const store = useAdminCurriculumStore();
const collapsed = ref(false);

const titleValue = computed({
  get: () => props.phase.draft_title ?? props.phase.title,
  set: (v: string) => store.putPhase(props.courseSlug, props.phase.phase_no, { title: v }),
});
const goalValue = computed({
  get: () => props.phase.draft_goal ?? props.phase.goal,
  set: (v: string) => store.putPhase(props.courseSlug, props.phase.phase_no, { goal: v }),
});
const systemPromptValue = computed({
  get: () => props.phase.draft_system_prompt ?? props.phase.system_prompt,
  set: (v: string) => store.putPhase(props.courseSlug, props.phase.phase_no, { system_prompt: v }),
});
</script>

<template>
  <section class="phase-edit" :data-test="`phase-edit-${phase.phase_no}`">
    <header @click="collapsed = !collapsed">
      <span class="toggle">{{ collapsed ? '▶' : '▼' }}</span>
      <h2>Phase {{ phase.phase_no }}: {{ phase.title }}</h2>
    </header>

    <div v-if="!collapsed" class="body">
      <label>
        <span class="lbl">title <span v-if="phase.draft_title !== null" class="ind">✏</span></span>
        <input v-model="titleValue" type="text" maxlength="200" />
      </label>
      <label>
        <span class="lbl">goal <span v-if="phase.draft_goal !== null" class="ind">✏</span></span>
        <input v-model="goalValue" type="text" maxlength="500" />
      </label>
      <label>
        <span class="lbl">system_prompt <span v-if="phase.draft_system_prompt !== null" class="ind">✏</span></span>
        <textarea v-model="systemPromptValue" rows="8" maxlength="8000" />
      </label>

      <CurriculumTaskEditor
        v-for="t in phase.tasks"
        :key="t.task_no"
        :course-slug="courseSlug"
        :phase-no="phase.phase_no"
        :task="t"
      />
    </div>
  </section>
</template>

<style scoped>
.phase-edit {
  border: 1px solid #d1d5db; border-radius: 12px;
  padding: 1rem 1.2rem; margin: 1rem 0;
  background: #f9fafb;
}
header {
  display: flex; align-items: baseline; gap: 0.6rem;
  cursor: pointer;
}
header h2 { margin: 0; font-size: 1rem; }
.toggle { color: #6b7280; }
.lbl { display: block; font-size: 0.85rem; color: #374151; margin-top: 0.6rem; }
.ind { color: #d97706; }
input, textarea {
  width: 100%;
  border: 1px solid #d1d5db; border-radius: 6px;
  padding: 0.4rem 0.6rem; font: inherit;
}
.body { display: flex; flex-direction: column; gap: 0.3rem; }
</style>
