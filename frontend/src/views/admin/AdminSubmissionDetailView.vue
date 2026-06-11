<script setup lang="ts">
/**
 * /admin/submissions/:id — single-submission drill-down.
 *
 * Bundles content + file list + grading history + comment thread. The
 * comment composer posts through the admin store, which mutates
 * selectedSubmission.comments in place — no refetch round-trip needed.
 */
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import CommentThread from '@/components/CommentThread.vue';
import { api } from '@/lib/api';
import { useAdminStore } from '@/stores/admin';

const route = useRoute();
const store = useAdminStore();

const submissionId = computed(() => String(route.params.id));
const postBusy = ref(false);
const downloadError = ref<string | null>(null);

async function load() {
  await store.fetchSubmissionDetail(submissionId.value);
}

onMounted(load);
watch(submissionId, load);

async function onPost(body: string) {
  postBusy.value = true;
  try {
    await store.postComment(submissionId.value, body);
  } finally {
    postBusy.value = false;
  }
}

async function downloadFile(fileId: string, filename: string) {
  downloadError.value = null;
  try {
    // Sprint 7 MED-3: the AdminSubmissionDetail payload carries
    // course_slug, so the download URL can scope ?course= to the
    // actual course this submission belongs to.
    const courseSlug = store.selectedSubmission?.course_slug ?? 'ai-driven-dev';
    const blob = await api.downloadFile(
      submissionId.value,
      fileId,
      courseSlug,
    );
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
      e instanceof Error ? e.message : 'ダウンロードに失敗しました';
  }
}
</script>

<template>
  <section class="panel">
    <RouterLink
      v-if="store.selectedSubmission"
      :to="{ name: 'admin-user-detail', params: { id: store.selectedSubmission.user_id } }"
      class="back"
    >
      ← {{ store.selectedSubmission.user_name }} さんの一覧へ
    </RouterLink>
    <RouterLink v-else to="/admin/users" class="back">← 受講者一覧へ</RouterLink>

    <p v-if="store.error" class="error">{{ store.error }}</p>

    <template v-if="store.selectedSubmission">
      <header class="head">
        <h1>
          Phase {{ store.selectedSubmission.phase }} / Task
          {{ store.selectedSubmission.task_no }}
        </h1>
        <div class="meta">
          <span class="who">{{ store.selectedSubmission.user_name }}</span>
          <span class="email">{{ store.selectedSubmission.user_email }}</span>
          <span class="score">
            {{
              store.selectedSubmission.score != null
                ? `${store.selectedSubmission.score} / 100`
                : '採点待ち'
            }}
          </span>
        </div>
      </header>

      <section class="block">
        <h2>提出本文</h2>
        <pre class="content">{{ store.selectedSubmission.content }}</pre>
      </section>

      <section v-if="store.selectedSubmission.files.length > 0" class="block">
        <h2>添付ファイル</h2>
        <ul class="files">
          <li v-for="f in store.selectedSubmission.files" :key="f.id">
            <button
              type="button"
              class="file-link"
              @click="downloadFile(f.id, f.filename)"
            >
              {{ f.filename }}
            </button>
            <span class="size">{{ Math.round(f.size_bytes / 1024) }} KB</span>
          </li>
        </ul>
        <p v-if="downloadError" class="error">{{ downloadError }}</p>
      </section>

      <section v-if="store.selectedSubmission.ai_feedback" class="block">
        <h2>AI フィードバック</h2>
        <p class="ai-feedback">{{ store.selectedSubmission.ai_feedback }}</p>
      </section>

      <section v-if="store.selectedSubmission.grading_history.length > 0" class="block">
        <h2>採点履歴</h2>
        <ul class="history">
          <li
            v-for="h in store.selectedSubmission.grading_history"
            :key="h.id"
            :class="`status-${h.status}`"
          >
            <span class="row-status">{{ h.status === 'graded' ? '採点' : '失敗' }}</span>
            <span class="row-score">
              {{ h.score != null ? `${h.score} 点` : '—' }}
            </span>
            <time>{{ new Date(h.created_at).toLocaleString('ja-JP') }}</time>
            <p v-if="h.feedback" class="feedback">{{ h.feedback }}</p>
            <p v-else-if="h.error_message" class="feedback err">
              {{ h.error_message }}
            </p>
          </li>
        </ul>
      </section>

      <section class="block">
        <h2>講師コメント</h2>
        <CommentThread
          :comments="store.selectedSubmission.comments"
          :can-post="true"
          :busy="postBusy"
          @post="onPost"
        />
      </section>
    </template>

    <p v-else-if="store.loading" class="loading">読み込み中…</p>
  </section>
</template>

<style scoped>
.panel {
  background: #fff;
  border-radius: 12px;
  padding: 1.4rem;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.06);
}
.back {
  display: inline-block;
  margin-bottom: 1rem;
  color: #4f46e5;
  text-decoration: none;
  font-size: 0.88rem;
}
.back:hover { text-decoration: underline; }
.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.7rem;
  border-bottom: 1px solid #e5e7eb;
  padding-bottom: 1rem;
}
h1 { margin: 0; font-size: 1.1rem; }
.meta {
  display: flex;
  align-items: baseline;
  gap: 0.7rem;
  font-size: 0.88rem;
}
.who { font-weight: 600; }
.email { color: #6b7280; }
.score { font-variant-numeric: tabular-nums; color: #1f2937; }
.block { margin-top: 1.4rem; }
.block h2 {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
}
.content {
  background: #f3f4f6;
  border-radius: 10px;
  padding: 0.8rem;
  font: inherit;
  white-space: pre-wrap;
  margin: 0;
}
.files {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.files li {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}
.file-link {
  background: none;
  border: 0;
  padding: 0;
  font: inherit;
  color: #4f46e5;
  text-decoration: underline;
  cursor: pointer;
}
.size { color: #6b7280; font-size: 0.82rem; }
.ai-feedback {
  background: #eef2ff;
  border-radius: 10px;
  padding: 0.8rem;
  margin: 0;
  font-size: 0.92rem;
}
.history {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.history li {
  background: #f9fafb;
  border-radius: 10px;
  padding: 0.6rem 0.8rem;
  display: grid;
  grid-template-columns: 60px auto 1fr;
  align-items: center;
  gap: 0.7rem;
}
.history li.status-failed { background: #fef2f2; }
.row-status {
  font-size: 0.78rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #4b5563;
}
.row-score { font-variant-numeric: tabular-nums; font-weight: 600; }
.history time { color: #6b7280; font-size: 0.82rem; text-align: right; }
.history .feedback {
  grid-column: 1 / -1;
  margin: 0.4rem 0 0;
  font-size: 0.92rem;
  white-space: pre-wrap;
}
.history .feedback.err { color: #b91c1c; }
.error {
  color: #b91c1c;
  font-size: 0.88rem;
  margin-top: 0.4rem;
}
.loading { color: #6b7280; font-size: 0.9rem; }
</style>
