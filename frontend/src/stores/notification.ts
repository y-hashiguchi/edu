/**
 * Sprint 4 in-app notification store (learner side).
 *
 * Drives the bell icon in the global header. Polling is opt-in via
 * `startPolling()` — App.vue starts it after login and stops it on
 * logout/unmount so unauthenticated traffic never hits the endpoint.
 *
 * `unreadCount` is exposed as state (not derived from items.length)
 * because the server caps `items` at notification_poll_limit (default 50)
 * while reporting the true unread total separately — using items.length
 * would silently under-count once the inbox passes the cap.
 */

import { defineStore } from 'pinia';

import { api } from '@/lib/api';
import type { NotificationOut } from '@/types/notification';

const POLL_INTERVAL_MS = 30_000;

interface State {
  items: NotificationOut[];
  unreadCount: number;
  pollHandle: number;
  error: string | null;
}

export const useNotificationStore = defineStore('notification', {
  state: (): State => ({
    items: [],
    unreadCount: 0,
    pollHandle: 0,
    error: null,
  }),
  getters: {
    hasUnread: (s) => s.unreadCount > 0,
  },
  actions: {
    async refresh() {
      try {
        const res = await api.listMyNotifications();
        this.items = res.items;
        this.unreadCount = res.unread_count;
        this.error = null;
      } catch (e) {
        // Poll errors are non-fatal — the next tick retries. Keep the
        // last good state so the badge doesn't flicker to 0 on a single
        // network hiccup.
        this.error = e instanceof Error ? e.message : 'unknown error';
      }
    },

    /**
     * Idempotent — calling startPolling() when already polling is a
     * no-op. Returns the interval handle for tests that want to assert
     * the timer was registered.
     */
    startPolling(): number {
      if (this.pollHandle !== 0) return this.pollHandle;
      // Refresh once immediately so the badge isn't blank for 30 s after
      // login.
      void this.refresh();
      this.pollHandle = window.setInterval(() => {
        void this.refresh();
      }, POLL_INTERVAL_MS);
      return this.pollHandle;
    },

    stopPolling() {
      if (this.pollHandle !== 0) {
        window.clearInterval(this.pollHandle);
        this.pollHandle = 0;
      }
    },

    async markRead(notificationId: string) {
      // Optimistic update: flip the row locally and decrement the badge
      // before the network call returns. On failure we re-fetch so the
      // truth wins back the UI.
      const idx = this.items.findIndex((n) => n.id === notificationId);
      const wasUnread = idx >= 0 && this.items[idx].read_at == null;
      if (wasUnread) {
        const now = new Date().toISOString();
        this.items = this.items.map((n, i) =>
          i === idx ? { ...n, read_at: now } : n,
        );
        this.unreadCount = Math.max(0, this.unreadCount - 1);
      }
      try {
        await api.markNotificationRead(notificationId);
      } catch (e) {
        this.error = e instanceof Error ? e.message : 'unknown error';
        await this.refresh();
        throw e;
      }
    },

    reset() {
      this.stopPolling();
      this.items = [];
      this.unreadCount = 0;
      this.error = null;
    },
  },
});
