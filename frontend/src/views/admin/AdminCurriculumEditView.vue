<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAdminCurriculumStore } from '@/stores/admin_curriculum';
import { api } from '@/lib/api';
import CurriculumPhaseEditor from '@/components/admin/CurriculumPhaseEditor.vue';
import type {
  AdminCurriculumCourseDetail,
  AdminPhaseEditOut,
  AdminTaskEditOut,
} from '@/types/admin_curriculum';

const route = useRoute();
const router = useRouter();
const store = useAdminCurriculumStore();

const slug = computed(() => String(route.params.courseSlug));

const showPublishModal = ref(false);
const showDiscardModal = ref(false);
const submitting = ref(false);
const loading = ref(false);
const loadError = ref<string | null>(null);
const message = ref<string | null>(null);

function countTaskDrafts(task: AdminTaskEditOut): number {
  let n = 0;
  if (task.draft_title !== null) n++;
  if (task.draft_description !== null) n++;
  if (task.draft_skill_tags !== null) n++;
  if (task.draft_deliverable !== null) n++;
  if (task.draft_week_label !== null) n++;
  return n;
}

function countPhaseDrafts(phase: AdminPhaseEditOut): number {
  let n = 0;
  if (phase.draft_title !== null) n++;
  if (phase.draft_goal !== null) n++;
  if (phase.draft_system_prompt !== null) n++;
  for (const t of phase.tasks) n += countTaskDrafts(t);
  return n;
}

const pendingDraftCount = computed(() => {
  const detail: AdminCurriculumCourseDetail | null = store.detail;
  if (!detail) return 0;
  return detail.phases.reduce((sum, p) => sum + countPhaseDrafts(p), 0);
});

onMounted(async () => {
  loading.value = true;
  loadError.value = null;
  try {
    await store.fetchDetail(slug.value);
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
  }
});

async function confirmPublish() {
  submitting.value = true;
  try {
    const result = await api.adminPublishCurriculum(slug.value);
    await store.fetchDetail(slug.value);
    message.value = `公開完了: ${result.published_phase_count} phase / ${result.published_task_count} task`;
    showPublishModal.value = false;
  } catch (e) {
    message.value = `公開失敗: ${e instanceof Error ? e.message : 'unknown'}`;
  } finally {
    submitting.value = false;
  }
}

async function confirmDiscard() {
  submitting.value = true;
  try {
    await store.discardDrafts(slug.value);
    message.value = 'ドラフトを破棄しました';
    showDiscardModal.value = false;
  } catch (e) {
    message.value = `破棄失敗: ${e instanceof Error ? e.message : 'unknown'}`;
  } finally {
    submitting.value = false;
  }
}

function backToList() {
  router.push({ name: 'admin-curriculum-list' });
}
</script>

<template>
  <main class="edit-view" data-test="admin-curriculum-edit-view">
    <header class="topbar">
      <button class="back" @click="backToList">← 一覧へ</button>
      <h1 v-if="store.detail">{{ store.detail.title }}</h1>
      <div class="actions" v-if="store.detail">
        <span class="pending" data-test="pending-count">
          ドラフト: {{ pendingDraftCount }} 件
        </span>
        <button
          class="discard"
          data-test="discard-button"
          :disabled="pendingDraftCount === 0 || submitting"
          @click="showDiscardModal = true"
        >
          ドラフト破棄
        </button>
        <button
          class="publish"
          data-test="publish-button"
          :disabled="pendingDraftCount === 0 || submitting"
          @click="showPublishModal = true"
        >
          公開
        </button>
      </div>
    </header>

    <p v-if="loading" class="loading">読み込み中…</p>
    <p v-if="loadError" class="error" data-test="error">{{ loadError }}</p>
    <p v-if="store.saveError" class="error" data-test="save-error">
      保存エラー: {{ store.saveError }}
    </p>
    <p v-if="message" class="message" data-test="message">{{ message }}</p>

    <section v-if="store.detail">
      <CurriculumPhaseEditor
        v-for="phase in store.detail.phases"
        :key="phase.phase_no"
        :course-slug="slug"
        :phase="phase"
      />
    </section>

    <div v-if="showPublishModal" class="modal" data-test="publish-modal">
      <div class="modal-card">
        <p>ドラフトを公開しますか？反映後は元に戻せません。</p>
        <div class="modal-actions">
          <button @click="showPublishModal = false" :disabled="submitting">キャンセル</button>
          <button class="primary" data-test="publish-confirm" @click="confirmPublish" :disabled="submitting">
            公開する
          </button>
        </div>
      </div>
    </div>

    <div v-if="showDiscardModal" class="modal" data-test="discard-modal">
      <div class="modal-card">
        <p>未公開のドラフトをすべて破棄しますか？</p>
        <div class="modal-actions">
          <button @click="showDiscardModal = false" :disabled="submitting">キャンセル</button>
          <button class="primary" data-test="discard-confirm" @click="confirmDiscard" :disabled="submitting">
            破棄する
          </button>
        </div>
      </div>
    </div>
  </main>
</template>

<style scoped>
.edit-view { max-width: 980px; margin: 0 auto; padding: 1.5rem; }
.topbar {
  display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;
  border-bottom: 1px solid #e5e7eb; padding-bottom: 0.8rem; margin-bottom: 1rem;
}
.topbar h1 { margin: 0; font-size: 1.25rem; flex: 1; }
.back { background: none; border: none; color: #2563eb; cursor: pointer; }
.actions { display: flex; gap: 0.5rem; align-items: center; }
.pending { font-size: 0.85rem; color: #6b7280; }
.discard, .publish {
  border: 1px solid #d1d5db; border-radius: 6px;
  padding: 0.4rem 0.8rem; cursor: pointer; background: white;
}
.discard:disabled, .publish:disabled { opacity: 0.5; cursor: not-allowed; }
.publish { background: #2563eb; color: white; border-color: #2563eb; }
.modal {
  position: fixed; inset: 0; background: rgba(0,0,0,0.4);
  display: flex; align-items: center; justify-content: center;
}
.modal-card {
  background: white; border-radius: 12px; padding: 1.5rem;
  max-width: 420px; width: 90%;
}
.modal-actions {
  display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 1rem;
}
.modal-actions button {
  border: 1px solid #d1d5db; border-radius: 6px;
  padding: 0.4rem 0.8rem; cursor: pointer; background: white;
}
.modal-actions .primary { background: #2563eb; color: white; border-color: #2563eb; }
.loading { color: #6b7280; }
.error { color: #b91c1c; }
.message { color: #047857; padding: 0.6rem; background: #ecfdf5; border-radius: 6px; }
</style>
