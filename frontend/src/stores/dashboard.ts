/**
 * Sprint 5 personalized dashboard store.
 *
 * Wraps GET /api/me/dashboard. The orchestrator on the backend is
 * relatively expensive (progress + weakness + RAG-backed recommendations
 * + LLM-generated nudge), so the UI calls `fetch()` on view mount and
 * uses `invalidate()` after events that change the underlying data
 * (e.g. a fresh submission) to force the next mount to re-fetch.
 */

import { defineStore } from 'pinia';

import { api } from '@/lib/api';
import type { DashboardResponse } from '@/types/dashboard';

interface State {
  data: DashboardResponse | null;
  loading: boolean;
  error: string | null;
}

export const useDashboardStore = defineStore('dashboard', {
  state: (): State => ({ data: null, loading: false, error: null }),
  actions: {
    async fetch(courseSlug: string) {
      this.loading = true;
      this.error = null;
      try {
        this.data = await api.getMyDashboard(courseSlug);
      } catch {
        // Backend errors here are non-actionable for the learner — they
        // just need to know the dashboard couldn't load. Detailed error
        // context is logged server-side.
        this.error = '読み込みに失敗しました';
      } finally {
        this.loading = false;
      }
    },
    invalidate() {
      this.data = null;
    },
  },
});
