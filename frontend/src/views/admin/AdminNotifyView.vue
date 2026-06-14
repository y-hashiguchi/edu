<script setup lang="ts">
/**
 * /admin/notify — compose notifications (1:1, immediate broadcast, or scheduled).
 */
import { computed, onMounted, ref } from 'vue';

import { api } from '@/lib/api';
import { useAdminStore } from '@/stores/admin';
import type { CourseCatalogItem } from '@/types/course';

const store = useAdminStore();

function defaultJstLocal(minutesAhead: number): string {
  const d = new Date(Date.now() + minutesAhead * 60_000 + 9 * 60 * 60_000);
  const jst = new Date(d.getTime());
  const pad = (n: number) => String(n).padStart(2, '0');
  return (
    `${jst.getUTCFullYear()}-${pad(jst.getUTCMonth() + 1)}-${pad(jst.getUTCDate())}` +
    `T${pad(jst.getUTCHours())}:${pad(jst.getUTCMinutes())}`
  );
}

function jstLocalToUtcIso(local: string): string {
  return new Date(`${local}:00+09:00`).toISOString();
}

function formatScheduledAt(iso: string): string {
  return new Date(iso).toLocaleString('ja-JP', { timeZone: 'Asia/Tokyo' });
}

const mode = ref<'single' | 'broadcast' | 'schedule'>('single');
const recipientId = ref('');
const courseSlug = ref('ai-driven-dev');
const courses = ref<CourseCatalogItem[]>([]);
const title = ref('');
const body = ref('');
const link = ref('');
const scheduledLocal = ref(defaultJstLocal(15));
const submitting = ref(false);
const successMessage = ref<string | null>(null);
const errorMessage = ref<string | null>(null);

onMounted(async () => {
  if (store.users.length === 0) {
    await store.fetchUsers(200, 0);
  }
  await store.fetchSentNotifications();
  await store.fetchScheduledBroadcasts('pending');
  const catalog = await api.listCourseCatalog();
  courses.value = catalog.items;
  if (catalog.items.length > 0 && !courseSlug.value) {
    courseSlug.value = catalog.items[0].slug;
  }
  scheduledLocal.value = defaultJstLocal(15);
});

const candidates = computed(() =>
  store.users.filter((u) => !u.is_admin),
);

const pendingScheduled = computed(() =>
  store.scheduledBroadcasts.filter((r) => r.status === 'pending'),
);

async function submit() {
  errorMessage.value = null;
  successMessage.value = null;
  if (!title.value.trim() || !body.value.trim()) {
    errorMessage.value = 'タイトルと本文を入力してください';
    return;
  }
  submitting.value = true;
  try {
    if (mode.value === 'single') {
      if (!recipientId.value) {
        errorMessage.value = '受講者を選択してください';
        return;
      }
      await store.sendNotification({
        recipient_user_id: recipientId.value,
        title: title.value.trim(),
        body: body.value.trim(),
        link: link.value.trim() ? link.value.trim() : null,
      });
      successMessage.value = '通知を送信しました';
    } else if (mode.value === 'broadcast') {
      if (!courseSlug.value) {
        errorMessage.value = 'コースを選択してください';
        return;
      }
      const res = await store.broadcastNotification({
        course_slug: courseSlug.value,
        title: title.value.trim(),
        body: body.value.trim(),
        link: link.value.trim() ? link.value.trim() : null,
      });
      successMessage.value =
        `一斉送信完了: ${res.sent_count} 件` +
        (res.skipped_inbox_full > 0
          ? `（受信上限でスキップ ${res.skipped_inbox_full} 件）`
          : '');
    } else {
      if (!courseSlug.value) {
        errorMessage.value = 'コースを選択してください';
        return;
      }
      if (!scheduledLocal.value) {
        errorMessage.value = '配信日時を入力してください';
        return;
      }
      await store.scheduleBroadcast({
        course_slug: courseSlug.value,
        title: title.value.trim(),
        body: body.value.trim(),
        link: link.value.trim() ? link.value.trim() : null,
        scheduled_at: jstLocalToUtcIso(scheduledLocal.value),
      });
      successMessage.value = '予約を登録しました';
      scheduledLocal.value = defaultJstLocal(15);
    }
    title.value = '';
    body.value = '';
    link.value = '';
  } catch (e) {
    errorMessage.value =
      e instanceof Error ? e.message : '送信に失敗しました';
  } finally {
    submitting.value = false;
  }
}

async function cancelScheduled(id: string) {
  errorMessage.value = null;
  try {
    await store.cancelScheduledBroadcast(id);
    successMessage.value = '予約をキャンセルしました';
  } catch (e) {
    errorMessage.value =
      e instanceof Error ? e.message : 'キャンセルに失敗しました';
  }
}

const submitLabel = computed(() => {
  if (submitting.value) return '送信中…';
  if (mode.value === 'single') return '送信する';
  if (mode.value === 'broadcast') return '一斉送信する';
  return '予約する';
});
</script>

<template>
  <section class="panel">
    <h1>通知作成</h1>

    <div class="mode-tabs">
      <button
        type="button"
        :class="{ active: mode === 'single' }"
        @click="mode = 'single'"
      >
        個別送信
      </button>
      <button
        type="button"
        :class="{ active: mode === 'broadcast' }"
        @click="mode = 'broadcast'"
      >
        即時一斉
      </button>
      <button
        type="button"
        data-test="mode-schedule"
        :class="{ active: mode === 'schedule' }"
        @click="mode = 'schedule'"
      >
        予約一斉
      </button>
    </div>

    <form @submit.prevent="submit">
      <label v-if="mode === 'single'" class="field">
        <span>宛先</span>
        <select v-model="recipientId" :disabled="submitting">
          <option value="" disabled>受講者を選択…</option>
          <option v-for="u in candidates" :key="u.id" :value="u.id">
            {{ u.name }} ({{ u.email }})
          </option>
        </select>
      </label>

      <label v-else class="field">
        <span>対象コース</span>
        <select v-model="courseSlug" :disabled="submitting">
          <option
            v-for="c in courses"
            :key="c.slug"
            :value="c.slug"
          >
            {{ c.title }}
          </option>
        </select>
      </label>

      <label v-if="mode === 'schedule'" class="field">
        <span>配信日時（日本時間 JST）</span>
        <input
          v-model="scheduledLocal"
          data-test="scheduled-at"
          type="datetime-local"
          :disabled="submitting"
        />
      </label>

      <label class="field">
        <span>タイトル</span>
        <input
          v-model="title"
          data-test="notify-title"
          type="text"
          maxlength="200"
          :disabled="submitting"
          placeholder="例: Phase 1 完了おめでとう"
        />
      </label>

      <label class="field">
        <span>本文</span>
        <textarea
          v-model="body"
          data-test="notify-body"
          rows="4"
          maxlength="2000"
          :disabled="submitting"
          placeholder="伝えたいメッセージを入力..."
        />
      </label>

      <label class="field">
        <span>リンク (任意)</span>
        <input
          v-model="link"
          type="text"
          maxlength="500"
          :disabled="submitting"
          placeholder="/courses/ai-driven-dev"
        />
      </label>

      <div class="actions">
        <p v-if="successMessage" class="ok">{{ successMessage }}</p>
        <p v-if="errorMessage" class="err">{{ errorMessage }}</p>
        <button type="submit" data-test="notify-submit" :disabled="submitting">
          {{ submitLabel }}
        </button>
      </div>
    </form>

    <section
      v-if="mode === 'schedule' && pendingScheduled.length > 0"
      class="outbox"
      data-test="scheduled-list"
    >
      <h2>予約一覧（pending）</h2>
      <ul>
        <li v-for="n in pendingScheduled" :key="n.id">
          <div class="row-head">
            <span class="title">{{ n.title }}</span>
            <time>{{ formatScheduledAt(n.scheduled_at) }}</time>
          </div>
          <p class="body">{{ n.body }}</p>
          <p class="meta">{{ n.course_slug }}</p>
          <button
            type="button"
            class="cancel-btn"
            @click="cancelScheduled(n.id)"
          >
            キャンセル
          </button>
        </li>
      </ul>
    </section>

    <section v-if="store.sentNotifications.length > 0" class="outbox">
      <h2>最近送った通知</h2>
      <ul>
        <li v-for="n in store.sentNotifications.slice(0, 10)" :key="n.id">
          <div class="row-head">
            <span class="title">{{ n.title }}</span>
            <time>{{ new Date(n.created_at).toLocaleString('ja-JP') }}</time>
          </div>
          <p class="body">{{ n.body }}</p>
        </li>
      </ul>
    </section>
  </section>
</template>

<style scoped>
.panel {
  background: #fff;
  border-radius: 12px;
  padding: 1.4rem;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.06);
  max-width: 640px;
}
h1 { margin: 0 0 1rem; font-size: 1.15rem; }
.mode-tabs {
  display: flex;
  gap: 0.4rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}
.mode-tabs button {
  border: 1px solid #d1d5db;
  background: #f9fafb;
  border-radius: 8px;
  padding: 0.35rem 0.75rem;
  font: inherit;
  cursor: pointer;
}
.mode-tabs button.active {
  background: #eef2ff;
  border-color: #818cf8;
  color: #4338ca;
  font-weight: 600;
}
form {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.88rem;
}
.field span {
  font-weight: 600;
  color: #374151;
}
.field input,
.field select,
.field textarea {
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0.55rem 0.7rem;
  font: inherit;
}
.field textarea { resize: vertical; }
.actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.7rem;
  margin-top: 0.5rem;
}
.actions button {
  background: var(--color-accent, #4f46e5);
  color: #fff;
  border: 0;
  border-radius: 10px;
  padding: 0.5rem 1.1rem;
  font: inherit;
  cursor: pointer;
}
.actions button:disabled { opacity: 0.5; cursor: not-allowed; }
.ok { color: #047857; font-size: 0.88rem; margin: 0; }
.err { color: #b91c1c; font-size: 0.88rem; margin: 0; }
.outbox { margin-top: 1.6rem; }
.outbox h2 { font-size: 0.95rem; margin: 0 0 0.6rem; }
.outbox ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.outbox li {
  background: #f9fafb;
  border-radius: 10px;
  padding: 0.7rem 0.9rem;
}
.row-head {
  display: flex;
  justify-content: space-between;
  font-size: 0.82rem;
  color: #6b7280;
  gap: 0.5rem;
}
.row-head .title { color: #1f2937; font-weight: 600; }
.outbox .body {
  margin: 0.3rem 0 0;
  font-size: 0.9rem;
  white-space: pre-wrap;
}
.meta {
  margin: 0.25rem 0 0;
  font-size: 0.78rem;
  color: #9ca3af;
}
.cancel-btn {
  margin-top: 0.4rem;
  border: 1px solid #fca5a5;
  background: #fff;
  color: #b91c1c;
  border-radius: 8px;
  padding: 0.25rem 0.6rem;
  font: inherit;
  cursor: pointer;
}
</style>
