<script setup lang="ts">
/**
 * CommentThread — shared comment listing used by admin and learner.
 *
 * Read-only by default. Pass `can-post` to render the composer at the
 * bottom; the parent owns the post action via the `post` emit so the
 * thread component never imports the api client directly.
 */
import { ref } from 'vue';

import type { AdminCommentOut, LearnerCommentOut } from '@/types/admin';

type Comment = AdminCommentOut | LearnerCommentOut;

const props = defineProps<{
  comments: Comment[];
  canPost?: boolean;
  busy?: boolean;
}>();

const emit = defineEmits<{
  post: [body: string];
}>();

const draft = ref('');
const localError = ref<string | null>(null);

function submit() {
  const trimmed = draft.value.trim();
  if (trimmed.length === 0) {
    localError.value = '本文を入力してください';
    return;
  }
  if (trimmed.length > 2000) {
    localError.value = '2000 文字以内で入力してください';
    return;
  }
  localError.value = null;
  emit('post', trimmed);
  draft.value = '';
}
</script>

<template>
  <section class="thread">
    <h2 v-if="comments.length === 0 && !canPost" class="empty">
      まだコメントはありません
    </h2>
    <ul v-if="comments.length > 0" class="list">
      <li v-for="c in comments" :key="c.id" class="row">
        <div class="head">
          <span class="who">{{ c.author_name }}</span>
          <time>{{ new Date(c.created_at).toLocaleString('ja-JP') }}</time>
        </div>
        <p class="body">{{ c.body }}</p>
      </li>
    </ul>

    <div v-if="canPost" class="composer">
      <label for="thread-body" class="sr-only">コメント本文</label>
      <textarea
        id="thread-body"
        v-model="draft"
        rows="3"
        placeholder="フィードバックを入力..."
        :disabled="busy"
      />
      <div class="actions">
        <span v-if="localError" class="error">{{ localError }}</span>
        <button type="button" :disabled="busy" @click="submit">
          {{ busy ? '送信中…' : 'コメントを送る' }}
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.thread {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}
.empty {
  color: #6b7280;
  font-size: 0.9rem;
  font-weight: 400;
  margin: 0;
}
.list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
}
.row {
  background: #f3f4f6;
  border-radius: 10px;
  padding: 0.7rem 0.9rem;
}
.head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.8rem;
  color: #4b5563;
}
.who {
  font-weight: 600;
  color: #1f2937;
}
time {
  font-variant-numeric: tabular-nums;
}
.body {
  margin: 0.4rem 0 0;
  font-size: 0.92rem;
  white-space: pre-wrap;
}
.composer {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.composer textarea {
  resize: vertical;
  min-height: 72px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0.5rem 0.7rem;
  font: inherit;
}
.composer .actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.7rem;
}
.composer .error {
  color: #b91c1c;
  font-size: 0.82rem;
}
.composer button {
  background: var(--color-accent, #4f46e5);
  color: #fff;
  border: 0;
  border-radius: 10px;
  padding: 0.45rem 1rem;
  font: inherit;
  cursor: pointer;
}
.composer button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
