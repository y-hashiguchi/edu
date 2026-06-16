<script setup lang="ts">
import { computed, ref } from 'vue';
import { useAdminCurriculumStore } from '@/stores/admin_curriculum';
import CurriculumTaskEditor from './CurriculumTaskEditor.vue';
import type { AdminPhaseEditOut } from '@/types/admin_curriculum';

const props = defineProps<{
  courseSlug: string;
  phase: AdminPhaseEditOut;
  phaseCount: number;
  canMoveUp: boolean;
  canMoveDown: boolean;
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

async function confirmDeletePhase() {
  if (props.phaseCount <= 1) return;
  if (!window.confirm(`Phase ${props.phase.phase_no} を削除しますか？\n提出がある Phase は削除できません。`)) {
    return;
  }
  await store.deletePhase(props.courseSlug, props.phase.phase_no);
}

function onMoveUp() {
  void store.movePhase(
    props.courseSlug,
    props.phase.phase_no,
    props.phase.phase_no - 1,
  );
}

function onMoveDown() {
  void store.movePhase(
    props.courseSlug,
    props.phase.phase_no,
    props.phase.phase_no + 1,
  );
}
</script>

<template>
  <section class="phase-edit" :data-test="`phase-edit-${phase.phase_no}`">
    <header @click="collapsed = !collapsed">
      <span class="toggle">{{ collapsed ? '▶' : '▼' }}</span>
      <h2>Phase {{ phase.phase_no }}: {{ phase.title }}</h2>
      <div class="phase-actions">
        <button
          type="button"
          class="phase-move"
          data-test="phase-move-up"
          :disabled="!canMoveUp"
          title="上へ"
          @click.stop="onMoveUp"
        >
          ↑
        </button>
        <button
          type="button"
          class="phase-move"
          data-test="phase-move-down"
          :disabled="!canMoveDown"
          title="下へ"
          @click.stop="onMoveDown"
        >
          ↓
        </button>
        <button
          v-if="phaseCount > 1"
          type="button"
          class="phase-delete"
          :data-test="`phase-delete-${phase.phase_no}`"
          @click.stop="confirmDeletePhase"
        >
          削除
        </button>
      </div>
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

      <div class="task-toolbar">
        <button
          type="button"
          class="add-task"
          data-test="add-task-btn"
          @click="store.addTask(courseSlug, phase.phase_no)"
        >
          + Task を追加
        </button>
      </div>

      <CurriculumTaskEditor
        v-for="t in phase.tasks"
        :key="t.task_no"
        :course-slug="courseSlug"
        :phase-no="phase.phase_no"
        :task="t"
        :task-count="phase.tasks.length"
        :can-move-up="t.task_no > 1"
        :can-move-down="t.task_no < phase.tasks.length"
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
header h2 { margin: 0; font-size: 1rem; flex: 1; }
.phase-actions { display: flex; gap: 0.35rem; margin-left: auto; }
.phase-move {
  border: 1px solid #d1d5db; border-radius: 6px;
  background: #fff; padding: 0.15rem 0.45rem; cursor: pointer; font: inherit;
}
.phase-move:disabled { opacity: 0.4; cursor: not-allowed; }
.phase-delete {
  border: 1px solid #fecaca; border-radius: 6px;
  background: #fef2f2; color: #b91c1c;
  padding: 0.2rem 0.5rem; font-size: 0.8rem; cursor: pointer;
}
.toggle { color: #6b7280; }
.lbl { display: block; font-size: 0.85rem; color: #374151; margin-top: 0.6rem; }
.ind { color: #d97706; }
input, textarea {
  width: 100%;
  border: 1px solid #d1d5db; border-radius: 6px;
  padding: 0.4rem 0.6rem; font: inherit;
}
.body { display: flex; flex-direction: column; gap: 0.3rem; }
.task-toolbar { display: flex; justify-content: flex-end; margin: 0.4rem 0; }
.add-task {
  border: 1px dashed #9ca3af; border-radius: 8px;
  background: #fff; padding: 0.35rem 0.75rem; cursor: pointer; font: inherit;
}
</style>
