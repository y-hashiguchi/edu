import { defineStore } from 'pinia';

import { api } from '@/lib/api';
import type { AdminCohortSummary } from '@/types/admin_cohort';

interface State {
  summary: AdminCohortSummary | null;
  labels: string[];
  loading: boolean;
  error: string | null;
  selectedSlug: string;
  selectedCohortLabel: string | null;
}

export const useAdminCohortStore = defineStore('admin_cohort', {
  state: (): State => ({
    summary: null,
    labels: [],
    loading: false,
    error: null,
    selectedSlug: 'ai-driven-dev',
    selectedCohortLabel: null,
  }),
  actions: {
    async fetchLabels(courseSlug: string) {
      try {
        const res = await api.adminCohortLabels(courseSlug);
        this.labels = res.items;
      } catch {
        this.labels = [];
      }
    },
    async fetchSummary(courseSlug: string, cohortLabel: string | null = null) {
      this.loading = true;
      this.error = null;
      this.selectedSlug = courseSlug;
      this.selectedCohortLabel = cohortLabel;
      try {
        await this.fetchLabels(courseSlug);
        this.summary = await api.adminCohortSummary(courseSlug, cohortLabel);
      } catch (e) {
        this.error = e instanceof Error ? e.message : String(e);
        this.summary = null;
      } finally {
        this.loading = false;
      }
    },
  },
});
