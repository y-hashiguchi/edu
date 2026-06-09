<script setup lang="ts">
/**
 * CommentThread — comment listing with nested replies (Sprint 6).
 *
 * Builds a tree from a flat comments array by parent_id, then renders
 * each branch via CommentThreadNode (recursive). The parent owns both
 * the trunk-post emit ('post') and the reply emit ('reply') so this
 * component never imports the api client directly.
 *
 * `canPost` (legacy Sprint 4 prop name) is admin's trunk composer.
 * `canReply` is the Sprint 6 addition for the learner reply button on
 * admin-authored comments.
 */
import { computed, ref } from 'vue';

import type { AdminCommentOut, LearnerCommentOut } from '@/types/admin';
import CommentThreadNode from '@/components/CommentThreadNode.vue';

type Comment = AdminCommentOut | LearnerCommentOut;

interface TreeNode {
  comment: Comment;
  children: TreeNode[];
}

const props = defineProps<{
  comments: Comment[];
  canPost?: boolean;
  canReply?: boolean;
  busy?: boolean;
}>();

const emit = defineEmits<{
  post: [body: string];
  reply: [payload: { parentId: string; body: string }];
}>();

function buildTree(items: Comment[]): TreeNode[] {
  const byId = new Map<string, TreeNode>();
  for (const c of items) byId.set(c.id, { comment: c, children: [] });
  const roots: TreeNode[] = [];
  for (const node of byId.values()) {
    const pid = node.comment.parent_id;
    if (pid && byId.has(pid)) byId.get(pid)!.children.push(node);
    else roots.push(node);
  }
  const sortRecursive = (nodes: TreeNode[]) => {
    nodes.sort(
      (a, b) =>
        new Date(a.comment.created_at).getTime() -
        new Date(b.comment.created_at).getTime(),
    );
    for (const n of nodes) sortRecursive(n.children);
  };
  sortRecursive(roots);
  return roots;
}

const tree = computed(() => buildTree(props.comments));

const draft = ref('');
const localError = ref<string | null>(null);

function submitTrunk() {
  const t = draft.value.trim();
  if (t.length === 0) {
    localError.value = '本文を入力してください';
    return;
  }
  if (t.length > 2000) {
    localError.value = '2000 文字以内で入力してください';
    return;
  }
  localError.value = null;
  emit('post', t);
  draft.value = '';
}

function onReply(payload: { parentId: string; body: string }) {
  emit('reply', payload);
}
</script>

<template>
  <section class="thread">
    <h2 v-if="comments.length === 0 && !canPost" class="empty">
      まだコメントはありません
    </h2>

    <CommentThreadNode
      v-for="node in tree"
      :key="node.comment.id"
      :node="node"
      :depth="0"
      :can-reply="canReply"
      @reply="onReply"
    />

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
        <button type="button" :disabled="busy" @click="submitTrunk">
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
  gap: 0.6rem;
}
.empty {
  color: #6b7280;
  font-size: 0.9rem;
  font-weight: 400;
  margin: 0;
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
