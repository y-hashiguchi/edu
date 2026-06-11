<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import CommentThread from '@/components/CommentThread.vue';
import FileUploadInput from '@/components/FileUploadInput.vue';
import GradingHistoryAccordion from '@/components/GradingHistoryAccordion.vue';
import { api } from '@/lib/api';
import type { LearnerCommentOut } from '@/types/admin';
import type { Submission } from '@/types/curriculum';

const downloadError = ref<string | null>(null);
// Comments live in the card's local state because the curriculum store
// only knows about the latest submission per task; comments are pulled
// once per submission render and on the prop watcher below if the
// submission id changes.
const comments = ref<LearnerCommentOut[]>([]);
const commentsError = ref<string | null>(null);
const replyBusy = ref(false);

const props = defineProps<{
  taskNo: number;
  taskText: string;
  submission?: Submission;
  busy: boolean;
  cooldownSeconds?: number;
  /** Sprint 7: needed by the file download endpoint. */
  courseSlug: string;
}>();

async function downloadFile(
  submissionId: string,
  fileId: string,
  filename: string,
): Promise<void> {
  downloadError.value = null;
  try {
    const blob = await api.downloadFile(submissionId, fileId, props.courseSlug);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    downloadError.value =
      e instanceof Error ? e.message : 'ファイルのダウンロードに失敗しました';
  }
}

const emit = defineEmits<{
  submit: [taskNo: number, content: string, files: File[]];
  regrade: [submissionId: string];
}>();

const draft = ref(props.submission?.content ?? '');
const pendingFiles = ref<File[]>([]);
const uploadRef = ref<InstanceType<typeof FileUploadInput> | null>(null);

watch(
  () => props.submission?.content,
  (v) => {
    if (v !== undefined) draft.value = v;
  },
);

async function loadComments(submissionId: string) {
  commentsError.value = null;
  try {
    comments.value = await api.listMySubmissionComments(submissionId);
  } catch (e) {
    comments.value = [];
    commentsError.value =
      e instanceof Error ? e.message : 'コメントの取得に失敗しました';
  }
}

async function onReply(payload: { parentId: string; body: string }) {
  // Sprint 6: 受講者から admin スレッドへの返信。投稿後にコメント一覧を
  // 再取得して、ベルアイコンと連動するつもりで楽観表示はしない。
  //
  // MED-5 (sprint-6 follow-up): clear any stale error at the top so
  // the previous failure does not appear to apply to the new attempt.
  // The replyBusy ref disables the submit button down the tree so a
  // double-tap cannot post two replies before the first round-trip
  // resolves.
  if (!props.submission) return;
  commentsError.value = null;
  replyBusy.value = true;
  try {
    await api.postMyReply(props.submission.id, payload.parentId, payload.body);
    await loadComments(props.submission.id);
  } catch (e) {
    commentsError.value =
      e instanceof Error ? e.message : '返信の送信に失敗しました';
  } finally {
    replyBusy.value = false;
  }
}

watch(
  () => props.submission?.id,
  (id) => {
    if (id) {
      void loadComments(id);
    } else {
      comments.value = [];
    }
  },
  { immediate: true },
);

const isGraded = computed(() => props.submission?.score != null);
const scoreLabel = computed(() =>
  isGraded.value ? `${props.submission!.score} / 100` : '採点中…',
);

const canRegrade = computed(
  () => props.submission != null && (props.cooldownSeconds ?? 0) === 0,
);

const sendDisabled = computed(() => props.busy || !draft.value.trim());

function send() {
  if (!draft.value.trim()) return;
  emit('submit', props.taskNo, draft.value.trim(), pendingFiles.value);
}

function regrade() {
  if (!props.submission) return;
  emit('regrade', props.submission.id);
}

function onFilesChange(files: File[]) {
  pendingFiles.value = files;
}

function clearFilesAfterSubmit() {
  if (uploadRef.value) uploadRef.value.reset();
  pendingFiles.value = [];
}

defineExpose({ clearFilesAfterSubmit });
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

    <FileUploadInput
      ref="uploadRef"
      :disabled="busy"
      @change="onFilesChange"
    />

    <div v-if="submission?.files?.length" class="attached">
      <strong>添付済み:</strong>
      <ul>
        <li v-for="f in submission.files" :key="f.id">
          <button
            type="button"
            class="link"
            @click="downloadFile(submission!.id, f.id, f.filename)"
          >
            {{ f.filename }}
          </button>
          <span class="meta">({{ Math.round(f.size_bytes / 1024) }} KB)</span>
        </li>
      </ul>
      <p v-if="downloadError" class="error">{{ downloadError }}</p>
    </div>

    <div v-if="submission?.ai_feedback" class="feedback">
      <strong>AI フィードバック:</strong>
      <p>{{ submission.ai_feedback }}</p>
    </div>

    <div class="actions">
      <button type="button" :disabled="sendDisabled" @click="send">
        {{ submission ? '再提出する' : '提出する' }}
      </button>
      <button
        v-if="submission"
        type="button"
        class="regrade"
        :disabled="busy || !canRegrade"
        @click="regrade"
      >
        再採点
        <span v-if="cooldownSeconds && cooldownSeconds > 0" class="cooldown">
          ({{ cooldownSeconds }}s)
        </span>
      </button>
    </div>

    <GradingHistoryAccordion
      v-if="submission"
      :history="submission.grading_history"
    />

    <section v-if="submission" class="comments">
      <h4>講師コメント</h4>
      <p v-if="commentsError" class="error">{{ commentsError }}</p>
      <CommentThread
        :comments="comments"
        :can-reply="true"
        :busy="replyBusy"
        @reply="onReply"
      />
    </section>
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
.num {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--color-accent);
}
.badge {
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 999px;
  background: #fef3c7;
  color: #92400e;
}
.badge.graded {
  background: #dcfce7;
  color: #166534;
}
.desc {
  margin: 0;
  font-size: 0.92rem;
}
textarea {
  resize: vertical;
  min-height: 88px;
  font: inherit;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0.6rem;
}
.attached {
  font-size: 0.85rem;
  color: #4b5563;
}
.attached ul {
  list-style: none;
  padding: 0;
  margin: 0.3rem 0 0;
}
.attached li {
  display: flex;
  gap: 0.4rem;
  align-items: center;
}
.attached .link {
  background: none;
  border: 0;
  padding: 0;
  color: var(--color-accent);
  text-decoration: underline;
  cursor: pointer;
  font: inherit;
}
.attached .link:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
.attached .error {
  color: #b91c1c;
  font-size: 0.8rem;
  margin: 0.3rem 0 0;
}
.attached .meta {
  font-size: 0.75rem;
  color: #9ca3af;
}
.feedback {
  background: #f9fafb;
  padding: 0.6rem 0.9rem;
  border-radius: 10px;
}
.feedback p {
  margin: 0.3rem 0 0;
  color: #374151;
  font-size: 0.9rem;
}
.actions {
  display: flex;
  gap: 0.5rem;
}
button {
  background: var(--color-accent);
  color: white;
  border: 0;
  border-radius: 10px;
  padding: 0.5rem 1rem;
  cursor: pointer;
  font: inherit;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
button.regrade {
  background: #fff;
  color: var(--color-accent);
  border: 1px solid var(--color-accent);
}
.cooldown {
  font-size: 0.75rem;
}
.comments {
  margin-top: 0.4rem;
  border-top: 1px dashed #e5e7eb;
  padding-top: 0.7rem;
}
.comments h4 {
  margin: 0 0 0.5rem;
  font-size: 0.85rem;
  color: #4b5563;
}
.comments .error {
  color: #b91c1c;
  font-size: 0.8rem;
  margin: 0 0 0.4rem;
}
</style>
