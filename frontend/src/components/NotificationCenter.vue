<script setup lang="ts">
/**
 * NotificationCenter — the bell icon + dropdown panel that lives in
 * the global header for logged-in learners.
 *
 * Polling lifecycle is owned here (not in App.vue) so the component
 * always has a consistent state at mount/unmount even when slotted
 * into a different layout later. The store's startPolling /
 * stopPolling actions are idempotent — a stray double-mount in
 * dev/HMR won't double the request rate.
 */
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { useNotificationStore } from '@/stores/notification';

const store = useNotificationStore();
const router = useRouter();
const open = ref(false);

onMounted(() => {
  store.startPolling();
});

onBeforeUnmount(() => {
  store.stopPolling();
});

function toggle() {
  open.value = !open.value;
}

function close() {
  open.value = false;
}

/**
 * HIGH-1 (sprint-4 security review): the backend already rejects
 * notifications with disallowed schemes at the DTO, but the SPA
 * re-validates as defence in depth. A stored notification predating
 * the backend fix, or a future regression, must not be able to embed
 * `javascript:` or `data:` URIs into the rendered anchor.
 */
const SAFE_LINK_RE = /^(https?:\/\/|\/)/i;

function isInternalLink(link: string | null): boolean {
  return typeof link === 'string' && link.startsWith('/') && SAFE_LINK_RE.test(link);
}

function safeExternalHref(link: string | null): string | undefined {
  if (typeof link !== 'string') return undefined;
  if (link.startsWith('/')) return undefined;
  if (!SAFE_LINK_RE.test(link)) return undefined;
  return link;
}

async function onItemClick(notificationId: string, link: string | null) {
  // Optimistic mark-read so the badge updates before the link
  // navigation kicks in. Even if the network roundtrip fails the
  // store rolls back on its own.
  try {
    await store.markRead(notificationId);
  } catch {
    // store already surfaced the error; nothing to do here.
  }
  close();
  if (isInternalLink(link)) {
    // MED-1 (sprint-4 security follow-up): resolve the link first and
    // refuse to push routes flagged `requiresAdmin`. Without this, an
    // admin-crafted notification with `link="/admin/users"` would
    // briefly flash the admin layout before attachAdminGuard kicked
    // the learner back to home. The router guard alone is enough for
    // authorisation, but UX-wise we never want learners to see the
    // admin chrome at all.
    const resolved = router.resolve(link as string);
    if (!resolved.meta?.requiresAdmin) {
      void router.push(link as string);
    }
  }
  // External links are handled entirely by the <a href> rendered in
  // the template (with rel="noopener noreferrer" target="_blank").
  // Unsafe schemes never reach the DOM because safeExternalHref()
  // returns undefined.
}
</script>

<template>
  <div class="nc" :class="{ open }">
    <button
      type="button"
      class="bell"
      :aria-label="`通知 ${store.unreadCount} 件未読`"
      :aria-expanded="open"
      @click="toggle"
    >
      <span class="icon" aria-hidden="true">🔔</span>
      <span v-if="store.hasUnread" class="badge">{{ store.unreadCount }}</span>
    </button>

    <div v-if="open" class="panel" role="dialog" aria-label="通知一覧">
      <header>
        <span>通知</span>
        <button type="button" class="close" aria-label="閉じる" @click="close">
          ×
        </button>
      </header>
      <p v-if="store.items.length === 0" class="empty">
        通知はありません。
      </p>
      <ul v-else>
        <li
          v-for="n in store.items"
          :key="n.id"
          :class="{ unread: n.read_at == null }"
        >
          <component
            :is="safeExternalHref(n.link) ? 'a' : 'button'"
            type="button"
            class="item"
            :href="safeExternalHref(n.link)"
            :target="safeExternalHref(n.link) ? '_blank' : undefined"
            :rel="safeExternalHref(n.link) ? 'noopener noreferrer' : undefined"
            @click="onItemClick(n.id, n.link)"
          >
            <div class="head">
              <strong class="title">{{ n.title }}</strong>
              <time>{{ new Date(n.created_at).toLocaleString('ja-JP') }}</time>
            </div>
            <p class="body">{{ n.body }}</p>
            <p class="from">from {{ n.sender_name }}</p>
          </component>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.nc {
  position: relative;
}
.bell {
  position: relative;
  background: transparent;
  border: 0;
  cursor: pointer;
  padding: 6px 8px;
  font-size: 1.25rem;
  border-radius: 8px;
}
.bell:hover { background: #f3f4f6; }
.badge {
  position: absolute;
  top: 0;
  right: 0;
  background: #ef4444;
  color: #fff;
  font-size: 0.7rem;
  font-weight: 700;
  min-width: 18px;
  padding: 1px 4px;
  border-radius: 999px;
  line-height: 1.3;
  text-align: center;
}
.panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 340px;
  max-height: 480px;
  overflow-y: auto;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.12);
  z-index: 50;
}
.panel header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.7rem 0.9rem;
  border-bottom: 1px solid #e5e7eb;
  font-weight: 600;
  font-size: 0.92rem;
}
.panel .close {
  background: transparent;
  border: 0;
  cursor: pointer;
  font-size: 1.1rem;
  line-height: 1;
  padding: 2px 6px;
  border-radius: 6px;
}
.panel .close:hover { background: #f3f4f6; }
.empty {
  padding: 1.2rem 1rem;
  text-align: center;
  color: #6b7280;
  font-size: 0.9rem;
  margin: 0;
}
.panel ul {
  list-style: none;
  padding: 0;
  margin: 0;
}
.panel li { border-bottom: 1px solid #f3f4f6; }
.panel li:last-child { border-bottom: 0; }
.panel li.unread { background: #eff6ff; }
.item {
  display: block;
  width: 100%;
  text-align: left;
  background: transparent;
  border: 0;
  padding: 0.7rem 0.9rem;
  cursor: pointer;
  color: inherit;
  text-decoration: none;
  font: inherit;
}
.item:hover { background: #f9fafb; }
.head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
}
.title { font-size: 0.92rem; }
.head time { font-size: 0.72rem; color: #6b7280; }
.body {
  margin: 0.3rem 0 0;
  font-size: 0.85rem;
  color: #374151;
  white-space: pre-wrap;
}
.from {
  margin: 0.3rem 0 0;
  font-size: 0.72rem;
  color: #9ca3af;
}
</style>
