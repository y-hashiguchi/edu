import { defineStore } from 'pinia';

import { api } from '@/lib/api';
import type { AdminCohortSummary } from '@/types/admin_cohort';

interface State {
  summary: AdminCohortSummary | null;
  loading: boolean;
  error: string | null;
  selectedSlug: string;
}

export const useAdminCohortStore = defineStore('admin_cohort', {
  state: (): State => ({
    summary: null,
    loading: false,
    error: null,
    selectedSlug: 'ai-driven-dev',
  }),
  actions: {
    async fetchSummary(courseSlug: string) {
      this.loading = true;
      this.error = null;
      this.selectedSlug = courseSlug;
      try {
        this.summary = await api.adminCohortSummary(courseSlug);
      } catch (e) {
        this.error = e instanceof Error ? e.message : String(e);
        this.summary = null;
      } finally {
        this.loading = false;
      }
    },
  },
});
