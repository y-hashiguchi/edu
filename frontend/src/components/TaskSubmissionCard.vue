<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import FileUploadInput from '@/components/FileUploadInput.vue';
import GradingHistoryAccordion from '@/components/GradingHistoryAccordion.vue';
import { api } from '@/lib/api';
import type { Submission } from '@/types/curriculum';

const downloadError = ref<string | null>(null);

async function downloadFile(
  submissionId: string,
  fileId: string,
  filename: string,
): Promise<void> {
  downloadError.value = null;
  try {
    const blob = await api.downloadFile(submissionId, fileId);
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

const props = defineProps<{
  taskNo: number;
  taskText: string;
  submission?: Submission;
  busy: boolean;
  cooldownSeconds?: number;
}>();

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
</style>
