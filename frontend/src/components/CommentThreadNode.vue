<script setup lang="ts">
/**
 * CommentThreadNode — single comment row with its nested children.
 *
 * Recursive. depth controls left-indent. Reply form is inline; clicking
 * "返信" expands the form, submit emits 'reply' upward through the tree.
 */
import { ref } from 'vue';

import type { AdminCommentOut, LearnerCommentOut } from '@/types/admin';

type Comment = AdminCommentOut | LearnerCommentOut;

interface TreeNode {
  comment: Comment;
  children: TreeNode[];
}

const props = defineProps<{
  node: TreeNode;
  depth: number;
  canReply?: boolean;
  busy?: boolean;
}>();

const emit = defineEmits<{
  reply: [payload: { parentId: string; body: string }];
}>();

const showForm = ref(false);
const draft = ref('');
const localError = ref<string | null>(null);

// 受講者は admin author を先祖に持つ comment にだけ返信可能。UI 簡略化
// として "current comment が admin 投稿か" を canReply と組み合わせて
// 判定する。完全な先祖チェックはサーバ側で行うため、UI はベストエフォート。
//
// Sprint 6: rely on the explicit is_admin_authored flag from the server
// (LearnerCommentOut), not on schema-level field presence. The previous
// `'author_user_id' in comment` duck-type check broke when
// LearnerCommentOut (correctly) omitted author_user_id for PII reasons
// — every learner view evaluated false and the reply button never
// rendered. The fallback to the field-presence check keeps admin views
// (AdminCommentOut still carries author_user_id) working unchanged.
const isAdminAuthored =
  'is_admin_authored' in props.node.comment
    ? (props.node.comment as { is_admin_authored: boolean }).is_admin_authored
    : 'author_user_id' in props.node.comment;
const canShowReplyButton = props.canReply && isAdminAuthored;

function open() {
  showForm.value = true;
  localError.value = null;
}

function cancel() {
  showForm.value = false;
  draft.value = '';
  localError.value = null;
}

function submit() {
  const t = draft.value.trim();
  if (t.length === 0) {
    localError.value = '本文を入力してください';
    return;
  }
  if (t.length > 2000) {
    localError.value = '2000 文字以内で入力してください';
    return;
  }
  emit('reply', { parentId: props.node.comment.id, body: t });
  draft.value = '';
  showForm.value = false;
  localError.value = null;
}

function bubbleReply(payload: { parentId: string; body: string }) {
  emit('reply', payload);
}
</script>

<template>
  <!-- MED-3 (sprint-6 follow-up): cap indent at depth 6 (96px). Deeper
       nodes are still rendered but stop indenting so a 50-deep thread
       doesn't push the body past the viewport. Server-side depth cap
       lives in services/comment.py:MAX_THREAD_DEPTH. -->
  <div class="node" :style="{ paddingLeft: `${Math.min(depth, 6) * 16}px` }">
    <div class="row">
      <div class="head">
        <span class="who">{{ node.comment.author_name }}</span>
        <time>
          {{ new Date(node.comment.created_at).toLocaleString('ja-JP') }}
        </time>
      </div>
      <p class="body">{{ node.comment.body }}</p>
      <button
        v-if="canShowReplyButton && !showForm"
        type="button"
        class="reply"
        @click="open"
      >
        返信する
      </button>

      <div v-if="showForm" class="reply-form">
        <textarea v-model="draft" class="reply-body" rows="2" />
        <div class="reply-actions">
          <span v-if="localError" class="error">{{ localError }}</span>
          <button type="button" class="reply-cancel" @click="cancel">
            キャンセル
          </button>
          <button
            type="button"
            class="reply-submit"
            :disabled="busy"
            @click="submit"
          >
            {{ busy ? '送信中…' : '送信' }}
          </button>
        </div>
      </div>
    </div>

    <CommentThreadNode
      v-for="child in node.children"
      :key="child.comment.id"
      :node="child"
      :depth="depth + 1"
      :can-reply="canReply"
      :busy="busy"
      @reply="bubbleReply"
    />
  </div>
</template>

<style scoped>
.node {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.row {
  background: #f3f4f6;
  border-radius: 10px;
  padding: 0.6rem 0.8rem;
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
button.reply {
  margin-top: 0.4rem;
  background: transparent;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 0.25rem 0.6rem;
  font: inherit;
  cursor: pointer;
  font-size: 0.8rem;
  color: #374151;
}
.reply-form {
  margin-top: 0.4rem;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.reply-body {
  resize: vertical;
  min-height: 60px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 0.4rem 0.6rem;
  font: inherit;
}
.reply-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.4rem;
}
.reply-cancel {
  background: transparent;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 0.3rem 0.7rem;
  font: inherit;
  cursor: pointer;
}
.reply-submit {
  background: var(--color-accent, #4f46e5);
  color: #fff;
  border: 0;
  border-radius: 8px;
  padding: 0.3rem 0.7rem;
  font: inherit;
  cursor: pointer;
}
.reply-submit:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.error {
  color: #b91c1c;
  font-size: 0.78rem;
}
</style>
