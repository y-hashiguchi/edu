/**
 * Sprint 4 admin dashboard store.
 *
 * Holds the four pieces the dashboard views read from:
 *   - users:             paginated learner list
 *   - selectedUser:      drill-down detail for the user in /admin/users/:id
 *   - submissions:       cross-cohort feed (filtered by user/phase)
 *   - selectedSubmission: detail view including comments thread
 *
 * Actions are thin wrappers over the api client — error handling lives
 * here so individual views don't have to reimplement try/catch around
 * every call. Views read `loading` / `error` to render spinners and
 * banners uniformly.
 */

import { defineStore } from 'pinia';

import { api } from '@/lib/api';
import type {
  AdminCommentOut,
  AdminDashboardResponse,
  AdminSubmissionDetail,
  AdminSubmissionListFilters,
  AdminSubmissionSummary,
  AdminUserDetail,
  AdminUserSummary,
} from '@/types/admin';
import type { NotificationCreatePayload, NotificationOut } from '@/types/notification';

interface State {
  users: AdminUserSummary[];
  usersTotal: number;
  selectedUser: AdminUserDetail | null;
  submissions: AdminSubmissionSummary[];
  submissionsTotal: number;
  selectedSubmission: AdminSubmissionDetail | null;
  sentNotifications: NotificationOut[];
  loading: boolean;
  error: string | null;
  // MED-4 (sprint-6 follow-up): dedicated field so the dashboard
  // section can show "load failed" without disturbing the rest of
  // the user-detail view.
  dashboardError: string | null;
}

function errString(e: unknown): string {
  return e instanceof Error ? e.message : 'unknown error';
}

export const useAdminStore = defineStore('admin', {
  state: (): State => ({
    users: [],
    usersTotal: 0,
    selectedUser: null,
    submissions: [],
    submissionsTotal: 0,
    selectedSubmission: null,
    sentNotifications: [],
    loading: false,
    error: null,
    dashboardError: null,
  }),
  actions: {
    async fetchUsers(limit = 50, offset = 0) {
      this.loading = true;
      this.error = null;
      try {
        const res = await api.adminListUsers(limit, offset);
        this.users = res.items;
        this.usersTotal = res.total;
      } catch (e) {
        this.error = errString(e);
      } finally {
        this.loading = false;
      }
    },

    async fetchUserDetail(userId: string) {
      this.loading = true;
      this.error = null;
      try {
        this.selectedUser = await api.adminGetUser(userId);
      } catch (e) {
        this.error = errString(e);
        this.selectedUser = null;
      } finally {
        this.loading = false;
      }
    },

    async fetchSubmissions(filters: AdminSubmissionListFilters = {}) {
      this.loading = true;
      this.error = null;
      try {
        const res = await api.adminListSubmissions(filters);
        this.submissions = res.items;
        this.submissionsTotal = res.total;
      } catch (e) {
        this.error = errString(e);
      } finally {
        this.loading = false;
      }
    },

    async fetchSubmissionDetail(submissionId: string) {
      this.loading = true;
      this.error = null;
      try {
        this.selectedSubmission = await api.adminGetSubmission(submissionId);
      } catch (e) {
        this.error = errString(e);
        this.selectedSubmission = null;
      } finally {
        this.loading = false;
      }
    },

    /**
     * Append a comment. Mutates `selectedSubmission.comments` in place
     * so the AdminSubmissionDetailView re-renders without a refetch —
     * one fewer round-trip per "post comment" interaction.
     */
    async postComment(submissionId: string, body: string): Promise<AdminCommentOut> {
      const comment = await api.adminPostComment(submissionId, body);
      if (this.selectedSubmission?.id === submissionId) {
        this.selectedSubmission = {
          ...this.selectedSubmission,
          comments: [...this.selectedSubmission.comments, comment],
        };
      }
      return comment;
    },

    async sendNotification(payload: NotificationCreatePayload) {
      const note = await api.adminSendNotification(payload);
      this.sentNotifications = [note, ...this.sentNotifications];
      return note;
    },

    async fetchSentNotifications() {
      const res = await api.adminListSentNotifications();
      this.sentNotifications = res.items;
    },

    /**
     * Sprint 6: admin が任意受講者の Sprint 5 dashboard (nudge 無し) を
     * 取得する。
     *
     * MED-4 (sprint-6 follow-up): エラーは store.dashboardError に
     * 残し、view が「データなし」と「読み込み失敗」を区別できるようにする。
     * silently null を返すと admin が「この受講者はまだ何もしていない」と
     * 誤認するため。
     */
    async fetchUserDashboard(
      userId: string,
      courseSlug: string,
    ): Promise<AdminDashboardResponse | null> {
      this.dashboardError = null;
      try {
        return await api.getAdminUserDashboard(userId, courseSlug);
      } catch (e) {
        this.dashboardError =
          e instanceof Error
            ? `受講者ダッシュボードの読み込みに失敗しました: ${e.message}`
            : '受講者ダッシュボードの読み込みに失敗しました';
        return null;
      }
    },
  },
});
