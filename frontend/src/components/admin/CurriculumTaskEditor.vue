<script setup lang="ts">
import { computed } from 'vue';
import { useAdminCurriculumStore } from '@/stores/admin_curriculum';
import SkillTagInput from './SkillTagInput.vue';
import type { AdminTaskEditOut } from '@/types/admin_curriculum';

const props = defineProps<{
  courseSlug: string;
  phaseNo: number;
  task: AdminTaskEditOut;
  taskCount: number;
  canMoveUp: boolean;
  canMoveDown: boolean;
}>();

const store = useAdminCurriculumStore();

const t = computed(() => props.task);

const titleValue = computed({
  get: () => t.value.draft_title ?? t.value.title,
  set: (v: string) => store.putTask(props.courseSlug, props.phaseNo, t.value.task_no, { title: v }),
});
const descValue = computed({
  get: () => t.value.draft_description ?? t.value.description,
  set: (v: string) => store.putTask(props.courseSlug, props.phaseNo, t.value.task_no, { description: v }),
});
const deliverableValue = computed({
  get: () => t.value.draft_deliverable ?? t.value.deliverable ?? '',
  set: (v: string) => store.putTask(props.courseSlug, props.phaseNo, t.value.task_no, { deliverable: v }),
});
const weekLabelValue = computed({
  get: () => t.value.draft_week_label ?? t.value.week_label ?? '',
  set: (v: string) => store.putTask(props.courseSlug, props.phaseNo, t.value.task_no, { week_label: v }),
});
const displayedTags = computed(() => t.value.draft_skill_tags ?? t.value.skill_tags);

function onTagsChange(tags: string[]) {
  store.putTask(props.courseSlug, props.phaseNo, t.value.task_no, { skill_tags: tags });
}

async function onDelete() {
  if (!window.confirm(`Task ${t.value.task_no} を削除しますか？`)) return;
  await store.deleteTask(props.courseSlug, props.phaseNo, t.value.task_no);
}

function onMoveUp() {
  void store.moveTask(
    props.courseSlug,
    props.phaseNo,
    t.value.task_no,
    t.value.task_no - 1,
  );
}

function onMoveDown() {
  void store.moveTask(
    props.courseSlug,
    props.phaseNo,
    t.value.task_no,
    t.value.task_no + 1,
  );
}
</script>

<template>
  <article class="task-edit" :data-test="`task-edit-${t.task_no}`">
    <header>
      <span class="num">Task {{ t.task_no }}</span>
      <div class="actions">
        <button
          type="button"
          class="btn"
          data-test="task-move-up"
          :disabled="!canMoveUp"
          title="上へ"
          @click="onMoveUp"
        >
          ↑
        </button>
        <button
          type="button"
          class="btn"
          data-test="task-move-down"
          :disabled="!canMoveDown"
          title="下へ"
          @click="onMoveDown"
        >
          ↓
        </button>
        <button
          type="button"
          class="btn danger"
          data-test="task-delete"
          :disabled="taskCount <= 1"
          title="削除"
          @click="onDelete"
        >
          削除
        </button>
      </div>
    </header>

    <label>
      <span class="lbl">title <span v-if="t.draft_title !== null" class="ind" data-test="title-draft-indicator">✏</span></span>
      <input
        v-model="titleValue"
        type="text"
        maxlength="200"
        data-test="task-title-input"
      />
    </label>

    <label>
      <span class="lbl">description <span v-if="t.draft_description !== null" class="ind">✏</span></span>
      <textarea v-model="descValue" rows="3" maxlength="2000" />
    </label>

    <label>
      <span class="lbl">skill_tags <span v-if="t.draft_skill_tags !== null" class="ind">✏</span></span>
      <SkillTagInput :tags="displayedTags" @change="onTagsChange" />
    </label>

    <div class="row">
      <label>
        <span class="lbl">deliverable <span v-if="t.draft_deliverable !== null" class="ind">✏</span></span>
        <input v-model="deliverableValue" type="text" maxlength="200" />
      </label>
      <label>
        <span class="lbl">week_label <span v-if="t.draft_week_label !== null" class="ind">✏</span></span>
        <input v-model="weekLabelValue" type="text" maxlength="200" />
      </label>
    </div>
  </article>
</template>

<style scoped>
.task-edit {
  border: 1px solid #e5e7eb; border-radius: 10px;
  padding: 0.8rem 1rem; margin: 0.5rem 0;
  display: flex; flex-direction: column; gap: 0.6rem;
}
header { display: flex; gap: 0.5rem; align-items: baseline; justify-content: space-between; }
.actions { display: flex; gap: 0.35rem; margin-left: auto; }
.btn {
  border: 1px solid #d1d5db; border-radius: 6px;
  background: #fff; padding: 0.15rem 0.45rem; cursor: pointer; font: inherit;
}
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.btn.danger { color: #b91c1c; border-color: #fca5a5; }
.num { font-weight: 700; color: #6b7280; }
.lbl { display: block; font-size: 0.85rem; color: #374151; margin-bottom: 0.25rem; }
.ind { color: #d97706; }
input, textarea {
  width: 100%;
  border: 1px solid #d1d5db; border-radius: 6px;
  padding: 0.4rem 0.6rem; font: inherit;
}
.row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.8rem; }
</style>
