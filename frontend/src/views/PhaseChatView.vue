<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useCurriculumStore } from '@/stores/curriculum';
import { useCourseStore } from '@/stores/course';
import ChatLog from '@/components/ChatLog.vue';
import ChatInput from '@/components/ChatInput.vue';
import SubmissionPanel from '@/components/SubmissionPanel.vue';
import { ApiCooldownError } from '@/lib/api';

/**
 * Sprint 7: every action on this view is course-scoped. The route
 * provides `courseSlug` and `phase` as props.
 */
const props = defineProps<{ courseSlug: string; phase: number }>();
const store = useCurriculumStore();
const course = useCourseStore();
const router = useRouter();

const sending = ref(false);
const sendError = ref<string | null>(null);
const confirmingComplete = ref(false);
const completing = ref(false);
const busyTaskNo = ref<number | null>(null);

const phaseData = computed(() => store.getPhase(props.phase));
const messages = computed(() => store.chatLogs[props.phase] ?? []);
const submissions = computed(() => store.submissions[props.phase] ?? []);
const quickQuestions = computed(() => phaseData.value?.tasks.slice(0, 3) ?? []);

const courseHomePath = computed(() => `/courses/${props.courseSlug}`);

const isLastPhase = computed(() => {
  // The "last" phase is course-dependent now. If the curriculum is
  // loaded use it; otherwise fall back to the historical default of 4.
  const phases = store.phases;
  if (phases.length === 0) return props.phase === 4;
  const maxPhase = Math.max(...phases.map((p) => p.phase));
  return props.phase === maxPhase;
});

const completionLabel = computed(() =>
  phaseData.value?.status === 'completed' ? '完了済み' : 'このフェーズを完了する',
);

onMounted(async () => {
  course.setActiveCourse(props.courseSlug);
  if (store.phases.length === 0) {
    await store.fetchPhasesWithProgress(props.courseSlug);
  }
  const data = store.getPhase(props.phase);
  if (!data) return;
  if (data.locked) {
    await router.push(courseHomePath.value);
    return;
  }
  await Promise.all([
    store.loadHistory(props.phase, props.courseSlug),
    store.loadSubmissions(props.phase, props.courseSlug),
  ]);
});

const submit = async (text: string) => {
  sending.value = true;
  sendError.value = null;
  try {
    await store.sendChat(props.phase, text, props.courseSlug);
  } catch (e) {
    sendError.value = e instanceof Error ? e.message : 'unknown error';
  } finally {
    sending.value = false;
  }
};

const submitTask = async (taskNo: number, content: string, files: File[]) => {
  busyTaskNo.value = taskNo;
  sendError.value = null;
  try {
    await store.submitTask(
      props.phase,
      taskNo,
      content,
      files,
      props.courseSlug,
    );
  } catch (e) {
    sendError.value = e instanceof Error ? e.message : 'unknown error';
  } finally {
    busyTaskNo.value = null;
  }
};

const regradeSubmission = async (submissionId: string) => {
  sendError.value = null;
  try {
    await store.regradeSubmission(props.phase, submissionId, props.courseSlug);
  } catch (e) {
    if (e instanceof ApiCooldownError) {
      sendError.value = `再採点はあと ${e.retryAfterSeconds} 秒お待ちください。`;
    } else {
      sendError.value = e instanceof Error ? e.message : 'unknown error';
    }
  }
};

const cooldownFor = (submissionId: string) =>
  store.cooldownSecondsRemaining(submissionId);

const openConfirm = () => {
  confirmingComplete.value = true;
};

const cancelConfirm = () => {
  confirmingComplete.value = false;
};

const confirmComplete = async () => {
  completing.value = true;
  try {
    await store.completePhase(props.phase, props.courseSlug);
    confirmingComplete.value = false;
    await router.push(courseHomePath.value);
  } catch (e) {
    sendError.value = e instanceof Error ? e.message : 'unknown error';
  } finally {
    completing.value = false;
  }
};
</script>

<template>
  <section v-if="!phaseData" class="loading">フェーズ情報を読み込み中…</section>
  <section v-else class="phase-chat">
    <header>
      <RouterLink :to="courseHomePath">← 一覧に戻る</RouterLink>
      <h2>Phase {{ phaseData.phase }} — {{ phaseData.title }}</h2>
      <p>{{ phaseData.goal }}</p>
    </header>

    <aside class="quick" v-if="quickQuestions.length > 0">
      <h3>クイック質問</h3>
      <button
        v-for="q in quickQuestions"
        :key="q"
        type="button"
        :disabled="sending"
        @click="submit(`課題について教えてください: ${q}`)"
      >
        {{ q }}
      </button>
    </aside>

    <ChatLog :messages="messages" />
    <p v-if="sending" class="thinking">AIが応答中…</p>
    <p v-if="sendError" class="error" role="alert">エラー: {{ sendError }}</p>
    <ChatInput :disabled="sending" @submit="submit" />

    <hr class="thin" />

    <SubmissionPanel
      :phase="phaseData"
      :submissions="submissions"
      :busy-task-no="busyTaskNo"
      :cooldown-for="cooldownFor"
      :course-slug="props.courseSlug"
      @submit="submitTask"
      @regrade="regradeSubmission"
    />

    <hr />

    <button
      type="button"
      class="complete-btn"
      :disabled="completing"
      @click="openConfirm"
    >
      {{ completionLabel }}
    </button>

    <div v-if="confirmingComplete" class="modal-backdrop" role="dialog" aria-modal="true">
      <div class="modal">
        <h3>Phase {{ phaseData.phase }} を完了しますか？</h3>
        <p v-if="!isLastPhase">
          完了すると Phase {{ phaseData.phase + 1 }} が解放されます。履歴は引き続き閲覧できます。
        </p>
        <p v-else>すべてのカリキュラムを終了します。履歴は引き続き閲覧できます。</p>
        <div class="actions">
          <button type="button" @click="cancelConfirm" :disabled="completing">キャンセル</button>
          <button
            type="button"
            class="primary"
            @click="confirmComplete"
            :disabled="completing"
          >
            {{ completing ? '完了処理中…' : '完了する' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.phase-chat { display: flex; flex-direction: column; gap: 1rem; }
.phase-chat header h2 { margin: 0.5rem 0 0.25rem; font-size: 1.2rem; }
.phase-chat header a { color: var(--color-accent); text-decoration: none; font-size: 0.9rem; }
.quick { display: flex; flex-direction: column; gap: 0.4rem; }
.quick h3 {
  margin: 0;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #6b7280;
}
.quick button {
  background: white;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0.6rem 0.9rem;
  text-align: left;
  cursor: pointer;
  font: inherit;
}
.quick button:hover { border-color: var(--color-accent); }
.quick button:disabled { opacity: 0.5; cursor: not-allowed; }
.error {
  background: #fee2e2;
  color: #991b1b;
  padding: 0.6rem 0.9rem;
  border-radius: 10px;
  margin: 0;
}
.loading { color: #6b7280; }
.thinking { color: #6b7280; font-size: 0.9rem; margin: 0; }
hr { border: 0; border-top: 1px solid #e5e7eb; margin: 1rem 0; }
hr.thin { margin: 0.5rem 0; }
.complete-btn {
  align-self: flex-start;
  background: var(--color-accent);
  color: white;
  border: 0;
  border-radius: 10px;
  padding: 0.7rem 1.2rem;
  font-weight: 600;
  cursor: pointer;
}
.complete-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}
.modal {
  background: white;
  padding: 1.5rem;
  border-radius: 16px;
  max-width: 420px;
  width: calc(100% - 2rem);
  box-shadow: 0 24px 48px rgba(15, 23, 42, 0.18);
}
.modal h3 { margin: 0 0 0.5rem; font-size: 1.05rem; }
.modal p { margin: 0 0 1rem; color: #374151; }
.actions { display: flex; justify-content: flex-end; gap: 0.5rem; }
.actions button {
  background: white;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0.5rem 0.9rem;
  cursor: pointer;
}
.actions button.primary {
  background: var(--color-accent);
  color: white;
  border-color: var(--color-accent);
}
.actions button:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
